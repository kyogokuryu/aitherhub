"""
product_detection_pipeline.py
─────────────────────────────
GPT-4V (Azure OpenAI) を使って動画フレームから商品/ブランドを検出し、
連続する検出結果を統合して商品タイムラインを生成する。

v2: プロンプト改善 + 音声照合強化 + スコアリング/フィルタリング

入力:
  - frame_dir   : 1秒ごとに抽出されたフレーム画像のディレクトリ
  - product_list : [{"product_name": "...", "brand_name": "...", "image_url": "..."}, ...]
  - transcription_segments : Whisperの文字起こし結果 (任意)

出力:
  - exposures : [{"product_name", "brand_name", "time_start", "time_end", "confidence"}, ...]
"""

import os
import re
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


# ─── BUILD PROMPT (v2: 精度改善) ───────────────────────────
def build_product_detection_prompt(product_list: list[dict]) -> str:
    """
    商品リストを含むシステムプロンプトを構築する。
    v2: 「配信者が積極的に紹介している商品」のみを検出するよう改善。
    """
    product_names = []
    for i, p in enumerate(product_list):
        name = p.get("product_name", p.get("name", p.get("商品名", p.get("商品タイトル", f"Product_{i}"))))
        brand = p.get("brand_name", p.get("brand", p.get("ブランド名", p.get("ブランド", ""))))
        if brand:
            product_names.append(f"- {name} ({brand})")
        else:
            product_names.append(f"- {name}")

    product_list_str = "\n".join(product_names)

    prompt = f"""あなたはライブコマース動画の商品検出AIです。
以下は、このライブ配信で販売されている商品リストです：

{product_list_str}

このフレーム画像を分析して、**配信者が現在アクティブに紹介・説明している商品**を上記リストから特定してください。

【重要な判定基準 — 以下の状態の商品のみを検出してください】
- 配信者が手に持っている商品 → confidence: 0.85〜0.95
- 配信者がカメラに向けて見せている商品 → confidence: 0.80〜0.95
- 画面の中央に大きく映っている商品（クローズアップ） → confidence: 0.75〜0.90
- 配信者が指差している・触れている商品 → confidence: 0.70〜0.85

【除外すべきもの — 検出しないでください】
- 背景や棚に並んでいるだけの商品
- テーブルの上に置いてあるが、配信者が触れていない商品
- 画面の端に小さく映っているだけの商品
- 前の紹介で使った後、脇に置かれた商品
- 配信者の後ろに見える商品ディスプレイ

【判断のポイント】
- 配信者の手や腕の位置に注目する
- 商品が画面のどの位置にあるか（中央=紹介中の可能性高い、端=背景の可能性高い）
- 商品のサイズ（大きく映っている=紹介中、小さい=背景）
- 配信者の体の向き（商品に向いている=紹介中）

JSON形式で返してください：
{{
  "detected_products": [
    {{
      "product_name": "商品名（リストと完全一致）",
      "confidence": 0.0〜1.0,
      "detection_reason": "hand_holding|showing_camera|closeup|pointing|background_only"
    }}
  ]
}}

配信者が商品を紹介していない場合は空配列を返してください：
{{"detected_products": []}}"""
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
                # v2: background_onlyを除外
                results = []
                for det in data["detected_products"]:
                    reason = det.get("detection_reason", "")
                    if reason == "background_only":
                        logger.debug("[PRODUCT] Skipping background-only: %s", det.get("product_name"))
                        continue
                    results.append(det)
                return results
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


# ─── MERGE DETECTIONS INTO TIMELINE (v2: 閾値引き上げ) ─────
def merge_detections_to_timeline(
    frame_detections: dict[int, list[dict]],
    sample_interval: int = 5,
    min_duration: float = 8.0,          # v2: 3.0 → 8.0（短い映り込みを除外）
    confidence_threshold: float = 0.5,   # v2: 0.3 → 0.5（低確信度を除外）
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
            reason = det.get("detection_reason", "")

            # v2: background_onlyは除外
            if reason == "background_only":
                continue

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


# ─── ENRICH WITH TRANSCRIPTION (v2: ペナルティ + 部分一致) ──
def enrich_with_transcription(
    exposures: list[dict],
    transcription_segments: list[dict],
    product_list: list[dict],
) -> list[dict]:
    """
    Whisperの文字起こしテキストから商品名の言及を検出し、
    既存のexposuresを補強する。

    v2 改善点:
    - 音声で言及されている商品 → confidenceを上げる（ブースト）
    - 音声で言及されていない商品 → confidenceを下げる（ペナルティ）
    - キーワード部分一致に対応（商品名を分割して照合）

    transcription_segments: [{"start": float, "end": float, "text": str}]
    """
    if not transcription_segments or not product_list:
        return exposures

    # 商品名のキーワードマップを構築（部分一致用に複数キーワード）
    product_keywords: dict[str, list[str]] = {}
    for p in product_list:
        name = p.get("product_name", p.get("name", p.get("商品名", p.get("商品タイトル", ""))))
        if not name:
            continue
        keywords = []
        # フルネーム
        keywords.append(name.lower())
        # ブランド名
        brand = p.get("brand_name", p.get("brand", p.get("ブランド名", p.get("ブランド", ""))))
        if brand:
            keywords.append(brand.lower())
        # 商品名を分割してキーワード化（3文字以上の単語）
        words = re.split(r'[\s　・/\-]+', name)
        for w in words:
            w = w.strip().lower()
            # 一般的すぎる単語を除外
            skip_words = {'kyogoku', 'the', 'and', 'for', 'pro', '用', '式', '型'}
            if len(w) >= 3 and w not in skip_words:
                keywords.append(w)
        product_keywords[name] = list(set(keywords))  # 重複排除

    def get_transcript_text(time_start: float, time_end: float, margin: float = 10.0) -> str:
        """指定時間帯のトランスクリプトテキストを取得（前後margin秒のバッファ付き）"""
        texts = []
        for seg in transcription_segments:
            seg_start = seg.get("start", 0)
            seg_end = seg.get("end", 0)
            if seg_end >= (time_start - margin) and seg_start <= (time_end + margin):
                texts.append(seg.get("text", ""))
        return " ".join(texts).lower()

    def check_audio_mention(product_name: str, transcript_text: str) -> tuple[bool, int]:
        """商品名が音声で言及されているかチェック。(言及あり, マッチ数)を返す"""
        if not transcript_text:
            return False, 0
        keywords = product_keywords.get(product_name, [product_name.lower()])
        match_count = 0
        for kw in keywords:
            if kw in transcript_text:
                match_count += 1
        return match_count > 0, match_count

    # ── v2: 既存のexposuresに音声スコアを適用 ──
    for exp in exposures:
        transcript_text = get_transcript_text(exp["time_start"], exp["time_end"])
        mentioned, match_count = check_audio_mention(exp["product_name"], transcript_text)

        if mentioned:
            # 音声で言及されている → confidenceを上げる
            boost = min(0.20, match_count * 0.08)
            exp["confidence"] = min(1.0, exp["confidence"] + boost)
            exp["audio_confirmed"] = True
            logger.debug(
                "[PRODUCT] Audio confirmed: %s (boost=%.2f, matches=%d)",
                exp["product_name"], boost, match_count,
            )
        else:
            # v2: 音声で言及されていない → confidenceを下げる（ペナルティ）
            original_conf = exp["confidence"]
            exp["confidence"] = round(exp["confidence"] * 0.6, 2)
            exp["audio_confirmed"] = False
            logger.debug(
                "[PRODUCT] Audio NOT confirmed: %s (%.2f → %.2f)",
                exp["product_name"], original_conf, exp["confidence"],
            )

    # ── v2: 音声のみの検出（映像で検出されなかったが音声で言及された商品）──
    audio_only_detections = []
    for seg in transcription_segments:
        text_lower = seg.get("text", "").lower()
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)

        for product_name, keywords in product_keywords.items():
            for kw in keywords:
                if kw in text_lower and len(kw) >= 3:
                    # この時間帯に既存のexposureがあるかチェック
                    already_exists = False
                    for exp in exposures:
                        if exp["product_name"] == product_name:
                            overlap = (
                                min(exp["time_end"], seg_end)
                                - max(exp["time_start"], seg_start)
                            )
                            if overlap > -10:
                                already_exists = True
                                break

                    if not already_exists:
                        audio_only_detections.append({
                            "product_name": product_name,
                            "brand_name": "",
                            "time_start": seg_start,
                            "time_end": seg_end,
                            "confidence": 0.55,
                            "audio_confirmed": True,
                        })
                    break  # 1つの商品につき1回だけ

    if audio_only_detections:
        logger.info("[PRODUCT] Audio-only detections: %d", len(audio_only_detections))
        exposures.extend(audio_only_detections)

    exposures.sort(key=lambda x: x["time_start"])
    return exposures


# ─── POST-FILTER (v2: 新規関数) ────────────────────────────
def post_filter_exposures(
    exposures: list[dict],
    final_confidence_threshold: float = 0.45,
    min_final_duration: float = 8.0,
) -> list[dict]:
    """
    v2: 音声スコアリング後の最終フィルタ。
    低confidenceのセグメントを除外する。
    """
    filtered = []
    removed = []
    for exp in exposures:
        duration = exp["time_end"] - exp["time_start"]
        conf = exp.get("confidence", 0)

        # 音声確認済みの場合は閾値を緩和
        if exp.get("audio_confirmed"):
            if conf >= 0.40 and duration >= 5.0:
                filtered.append(exp)
            else:
                removed.append(exp)
        else:
            # 映像のみの場合は厳しめ
            if conf >= final_confidence_threshold and duration >= min_final_duration:
                filtered.append(exp)
            else:
                removed.append(exp)

    if removed:
        logger.info(
            "[PRODUCT] Post-filter removed %d segments (kept %d)",
            len(removed), len(filtered),
        )
        for r in removed[:5]:  # 最初の5件だけログ
            logger.debug(
                "[PRODUCT]   Removed: %s (conf=%.2f, dur=%.0fs, audio=%s)",
                r["product_name"], r.get("confidence", 0),
                r["time_end"] - r["time_start"],
                r.get("audio_confirmed", False),
            )

    return filtered


# ─── FILL BRAND NAMES ──────────────────────────────────────
def fill_brand_names(exposures: list[dict], product_list: list[dict]) -> list[dict]:
    """product_listからbrand_nameとimage_urlを補完する"""
    name_to_info: dict[str, dict] = {}
    for p in product_list:
        name = p.get("product_name", p.get("name", p.get("商品名", p.get("商品タイトル", ""))))
        if name:
            name_to_info[name] = {
                "brand_name": p.get("brand_name", p.get("brand", p.get("ブランド名", p.get("ブランド", "")))),
                "image_url": p.get("image_url", p.get("product_image_url", "")),
            }

    for exp in exposures:
        info = name_to_info.get(exp["product_name"], {})
        exp["brand_name"] = info.get("brand_name", "")
        exp["product_image_url"] = info.get("image_url", "")

    return exposures


# ─── MAIN ENTRY POINT (v2: post_filter追加) ─────────────────
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

    # 文字起こしで補強 + ペナルティ
    if transcription_segments:
        exposures = enrich_with_transcription(
            exposures, transcription_segments, product_list,
        )
        logger.info("[PRODUCT] After audio enrichment: %d segments", len(exposures))

    # v2: 最終フィルタ（低confidence + 短時間のセグメントを除外）
    exposures = post_filter_exposures(exposures)
    logger.info("[PRODUCT] After post-filter: %d segments", len(exposures))

    # ブランド名とimage_urlを補完
    exposures = fill_brand_names(exposures, product_list)

    return exposures
