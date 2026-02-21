"""
product_detection_pipeline.py
─────────────────────────────
GPT-4V (Azure OpenAI) を使って動画フレームから商品/ブランドを検出し、
連続する検出結果を統合して商品タイムラインを生成する。

入力:
  - frame_dir   : 1秒ごとに抽出されたフレーム画像のディレクトリ
  - product_list : [{"product_name": "...", "brand_name": "...", "image_url": "..."}, ...]
  - transcription_segments : Whisperの文字起こし結果 (任意)

出力:
  - exposures : [{"product_name", "brand_name", "time_start", "time_end", "confidence"}, ...]
"""

import os
import json
import time
import random
import base64
import asyncio
import logging
from functools import partial
from openai import AzureOpenAI, RateLimitError, APIError, APITimeoutError
from dotenv import load_dotenv
from decouple import config

load_dotenv()
logger = logging.getLogger("product_detection")

# ─── ENV & CLIENT ───────────────────────────────────────────
MAX_CONCURRENCY = 3  # conservative to avoid 429

def env(key, default=None):
    return os.getenv(key) or config(key, default=default)

OPENAI_API_KEY = env("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = env("AZURE_OPENAI_ENDPOINT")
GPT5_API_VERSION = env("GPT5_API_VERSION")
GPT5_MODEL = env("GPT5_MODEL")

client = AzureOpenAI(
    api_key=OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=GPT5_API_VERSION,
)


# ─── UTILS ──────────────────────────────────────────────────
def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def safe_json_load(text: str):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ─── BUILD PROMPT ───────────────────────────────────────────
def build_product_detection_prompt(product_list: list[dict]) -> str:
    """
    商品リストを含むシステムプロンプトを構築する。
    GPT-4Vに「このフレームに映っている商品をリストから選べ」と指示する。
    """
    product_names = []
    for i, p in enumerate(product_list):
        name = p.get("product_name", p.get("name", f"Product_{i}"))
        brand = p.get("brand_name", p.get("brand", ""))
        if brand:
            product_names.append(f"- {name} ({brand})")
        else:
            product_names.append(f"- {name}")

    product_list_str = "\n".join(product_names)

    prompt = f"""あなたはライブコマース動画の商品検出AIです。
以下は、このライブ配信で販売されている商品リストです：

{product_list_str}

このフレーム画像を分析して、画面に映っている商品を上記リストから特定してください。

ルール：
1. 商品パッケージ、ロゴ、テキスト、形状などの視覚的手がかりを使って判断する
2. 商品が映っていない場合は空配列を返す
3. 確信度が低い場合でも、最も可能性の高い商品を返す（confidenceで表現）
4. 複数の商品が同時に映っている場合は全て返す

JSON形式で返してください：
{{
  "detected_products": [
    {{
      "product_name": "商品名（リストと完全一致）",
      "confidence": 0.0〜1.0
    }}
  ]
}}"""
    return prompt


# ─── SINGLE FRAME DETECTION ────────────────────────────────
def detect_products_in_frame(image_path: str, prompt: str) -> list[dict]:
    """1フレームの商品検出（同期）"""
    img_b64 = encode_image(image_path)

    for attempt in range(5):
        try:
            resp = client.responses.create(
                model=GPT5_MODEL,
                input=[{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{img_b64}",
                        },
                    ],
                }],
                max_output_tokens=512,
            )
            data = safe_json_load(resp.output_text)
            if data and "detected_products" in data:
                return data["detected_products"]
            return []
        except (RateLimitError, APITimeoutError):
            sleep_time = (2 ** attempt) + random.uniform(0, 1)
            logger.warning("[PRODUCT] Rate limit, retry in %.1fs (attempt %d)", sleep_time, attempt + 1)
            time.sleep(sleep_time)
        except (APIError, Exception) as e:
            logger.warning("[PRODUCT] API error on %s: %s", os.path.basename(image_path), e)
            return []
    return []


async def detect_products_in_frame_async(
    image_path: str,
    prompt: str,
    sem: asyncio.Semaphore,
) -> list[dict]:
    """1フレームの商品検出（非同期ラッパー）"""
    async with sem:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(detect_products_in_frame, image_path, prompt),
        )


# ─── SAMPLING STRATEGY ─────────────────────────────────────
def select_sample_frames(
    files: list[str],
    sample_interval: int = 5,
) -> list[int]:
    """
    全フレームではなく、N秒ごとにサンプリングしてAPI呼び出しを削減。
    例: 600フレーム（10分動画）→ 120フレーム（5秒間隔）
    """
    indices = list(range(0, len(files), sample_interval))
    # 最後のフレームも含める
    if indices and indices[-1] != len(files) - 1:
        indices.append(len(files) - 1)
    return indices


# ─── MERGE DETECTIONS INTO TIMELINE ────────────────────────
def merge_detections_to_timeline(
    frame_detections: dict[int, list[dict]],
    sample_interval: int = 5,
    min_duration: float = 3.0,
    confidence_threshold: float = 0.3,
) -> list[dict]:
    """
    フレームごとの検出結果を統合して、連続する商品露出セグメントを生成する。

    frame_detections: {frame_index: [{"product_name": ..., "confidence": ...}]}

    Returns: [{"product_name", "brand_name", "time_start", "time_end", "confidence"}]
    """
    if not frame_detections:
        return []

    # フレームインデックスをソート
    sorted_frames = sorted(frame_detections.keys())

    # 商品ごとに出現フレームを集約
    product_frames: dict[str, list[tuple[int, float]]] = {}
    for fidx in sorted_frames:
        for det in frame_detections[fidx]:
            name = det.get("product_name", "")
            conf = det.get("confidence", 0.5)
            if not name or conf < confidence_threshold:
                continue
            if name not in product_frames:
                product_frames[name] = []
            product_frames[name].append((fidx, conf))

    # 各商品について連続区間を検出
    exposures = []
    for product_name, frames in product_frames.items():
        if not frames:
            continue

        # フレームをソート
        frames.sort(key=lambda x: x[0])

        # 連続区間をグループ化（gap_tolerance = sample_interval * 2）
        gap_tolerance = sample_interval * 2 + 1
        segments = []
        seg_start = frames[0][0]
        seg_end = frames[0][0]
        seg_confs = [frames[0][1]]

        for i in range(1, len(frames)):
            fidx, conf = frames[i]
            if fidx - seg_end <= gap_tolerance:
                # 連続している
                seg_end = fidx
                seg_confs.append(conf)
            else:
                # ギャップ → 新しいセグメント
                segments.append((seg_start, seg_end, seg_confs))
                seg_start = fidx
                seg_end = fidx
                seg_confs = [conf]

        segments.append((seg_start, seg_end, seg_confs))

        # セグメントをexposureに変換
        for start_frame, end_frame, confs in segments:
            time_start = float(start_frame)
            time_end = float(end_frame + sample_interval)  # 次のサンプルまで延長
            duration = time_end - time_start

            if duration < min_duration:
                continue

            avg_conf = sum(confs) / len(confs)

            exposures.append({
                "product_name": product_name,
                "brand_name": "",  # 後でproduct_listからマッチ
                "time_start": time_start,
                "time_end": time_end,
                "confidence": round(avg_conf, 2),
            })

    # time_startでソート
    exposures.sort(key=lambda x: x["time_start"])
    return exposures


# ─── ENRICH WITH TRANSCRIPTION ──────────────────────────────
def enrich_with_transcription(
    exposures: list[dict],
    transcription_segments: list[dict],
    product_list: list[dict],
) -> list[dict]:
    """
    Whisperの文字起こしテキストから商品名の言及を検出し、
    既存のexposuresを補強する。

    transcription_segments: [{"start": float, "end": float, "text": str}]
    """
    if not transcription_segments or not product_list:
        return exposures

    # 商品名のキーワードマップを構築
    product_keywords: dict[str, str] = {}
    for p in product_list:
        name = p.get("product_name", p.get("name", ""))
        if not name:
            continue
        # 商品名の一部をキーワードとして登録
        product_keywords[name.lower()] = name
        # ブランド名もキーワードに追加
        brand = p.get("brand_name", p.get("brand", ""))
        if brand:
            product_keywords[brand.lower()] = name

    # 文字起こしテキストから商品名の言及を検出
    audio_detections = []
    for seg in transcription_segments:
        text_lower = seg.get("text", "").lower()
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)

        for keyword, product_name in product_keywords.items():
            if keyword in text_lower:
                audio_detections.append({
                    "product_name": product_name,
                    "time_start": seg_start,
                    "time_end": seg_end,
                    "confidence": 0.7,
                    "source": "audio",
                })

    if not audio_detections:
        return exposures

    # 既存のexposuresと音声検出を統合
    # 同じ商品が同じ時間帯にある場合はconfidenceを上げる
    for audio_det in audio_detections:
        merged = False
        for exp in exposures:
            if exp["product_name"] == audio_det["product_name"]:
                # 時間帯が重なっているか近い場合
                overlap = (
                    min(exp["time_end"], audio_det["time_end"])
                    - max(exp["time_start"], audio_det["time_start"])
                )
                if overlap > -10:  # 10秒以内のギャップも統合
                    # confidenceを上げる
                    exp["confidence"] = min(1.0, exp["confidence"] + 0.15)
                    # 時間範囲を拡張
                    exp["time_start"] = min(exp["time_start"], audio_det["time_start"])
                    exp["time_end"] = max(exp["time_end"], audio_det["time_end"])
                    merged = True
                    break

        if not merged:
            # 新しいexposureとして追加（音声のみの検出）
            exposures.append({
                "product_name": audio_det["product_name"],
                "brand_name": "",
                "time_start": audio_det["time_start"],
                "time_end": audio_det["time_end"],
                "confidence": audio_det["confidence"],
            })

    exposures.sort(key=lambda x: x["time_start"])
    return exposures


# ─── FILL BRAND NAMES ──────────────────────────────────────
def fill_brand_names(exposures: list[dict], product_list: list[dict]) -> list[dict]:
    """product_listからbrand_nameとimage_urlを補完する"""
    name_to_info: dict[str, dict] = {}
    for p in product_list:
        name = p.get("product_name", p.get("name", ""))
        if name:
            name_to_info[name] = {
                "brand_name": p.get("brand_name", p.get("brand", "")),
                "image_url": p.get("image_url", p.get("product_image_url", "")),
            }

    for exp in exposures:
        info = name_to_info.get(exp["product_name"], {})
        exp["brand_name"] = info.get("brand_name", "")
        exp["product_image_url"] = info.get("image_url", "")

    return exposures


# ─── MAIN ENTRY POINT ──────────────────────────────────────
def detect_product_timeline(
    frame_dir: str,
    product_list: list[dict],
    transcription_segments: list[dict] | None = None,
    sample_interval: int = 5,
    on_progress=None,
) -> list[dict]:
    """
    商品タイムライン検出のメインエントリポイント。

    Args:
        frame_dir: フレーム画像のディレクトリ
        product_list: 商品リスト [{"product_name", "brand_name", ...}]
        transcription_segments: Whisper文字起こし結果 (任意)
        sample_interval: サンプリング間隔（秒）
        on_progress: 進捗コールバック (0-100)

    Returns:
        exposures: [{"product_name", "brand_name", "time_start", "time_end",
                     "confidence", "product_image_url"}]
    """
    if not product_list:
        logger.warning("[PRODUCT] No product list provided, skipping detection")
        return []

    files = sorted([f for f in os.listdir(frame_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    if not files:
        logger.warning("[PRODUCT] No frames found in %s", frame_dir)
        return []

    logger.info(
        "[PRODUCT] Starting detection: %d frames, %d products, interval=%ds",
        len(files), len(product_list), sample_interval,
    )

    # プロンプトを構築
    prompt = build_product_detection_prompt(product_list)

    # サンプルフレームを選択
    sample_indices = select_sample_frames(files, sample_interval)
    total_samples = len(sample_indices)
    logger.info("[PRODUCT] Sampling %d frames (out of %d total)", total_samples, len(files))

    # 非同期で商品検出を実行
    frame_detections: dict[int, list[dict]] = {}
    completed = [0]

    async def run_detection():
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = []

        for fidx in sample_indices:
            image_path = os.path.join(frame_dir, files[fidx])

            async def _detect(idx=fidx, path=image_path):
                result = await detect_products_in_frame_async(path, prompt, sem)
                frame_detections[idx] = result
                completed[0] += 1
                if on_progress and total_samples > 0:
                    pct = min(int(completed[0] / total_samples * 100), 100)
                    on_progress(pct)

            tasks.append(_detect())

        await asyncio.gather(*tasks)

    # イベントループを実行
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, run_detection()).result()
        else:
            loop.run_until_complete(run_detection())
    except RuntimeError:
        asyncio.run(run_detection())

    logger.info(
        "[PRODUCT] Detection complete: %d frames processed, %d had products",
        len(frame_detections),
        sum(1 for v in frame_detections.values() if v),
    )

    # 検出結果をタイムラインに統合
    exposures = merge_detections_to_timeline(
        frame_detections,
        sample_interval=sample_interval,
    )
    logger.info("[PRODUCT] Merged into %d exposure segments", len(exposures))

    # 文字起こしで補強
    if transcription_segments:
        exposures = enrich_with_transcription(
            exposures, transcription_segments, product_list,
        )
        logger.info("[PRODUCT] After audio enrichment: %d segments", len(exposures))

    # ブランド名とimage_urlを補完
    exposures = fill_brand_names(exposures, product_list)

    return exposures
