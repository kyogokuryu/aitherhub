"""
Video processing progress calculation utilities.
"""

# Upload progress contribution (0-20%)
UPLOAD_PROGRESS = 20

def calculate_progress(status: str) -> int:
    """
    Calculate progress percentage based on current video processing status.

    Progress mapping accounts for:
    - Upload phase: 0-20%
    - Processing steps: 20-100%

    Args:
        status: Current video status (e.g., 'STEP_0_EXTRACT_FRAMES', 'DONE', etc.)

    Returns:
        Progress percentage (0-100). Returns -1 for ERROR status.

    Examples:
        >>> calculate_progress('uploaded')
        20
        >>> calculate_progress('STEP_5_BUILD_PHASE_UNITS')
        60
        >>> calculate_progress('DONE')
        100
        >>> calculate_progress('ERROR')
        -1
    """
    status_map = {
        "NEW": 0,
        "uploaded": UPLOAD_PROGRESS,  # Upload complete at 20%
        "STEP_0_EXTRACT_FRAMES": 25,
        "STEP_1_DETECT_PHASES": 30,
        "STEP_2_EXTRACT_METRICS": 40,
        "STEP_3_TRANSCRIBE_AUDIO": 50,
        "STEP_4_IMAGE_CAPTION": 55,
        "STEP_5_BUILD_PHASE_UNITS": 65,
        "STEP_6_BUILD_PHASE_DESCRIPTION": 70,
        "STEP_7_GROUPING": 75,
        "STEP_8_UPDATE_BEST_PHASE": 80,
        "STEP_9_BUILD_VIDEO_STRUCTURE_FEATURES": 85,
        "STEP_10_ASSIGN_VIDEO_STRUCTURE_GROUP": 88,
        "STEP_11_UPDATE_VIDEO_STRUCTURE_GROUP_STATS": 91,
        "STEP_12_UPDATE_VIDEO_STRUCTURE_BEST": 94,
        "STEP_13_BUILD_REPORTS": 97,
        "STEP_14_SPLIT_VIDEO": 99,
        "DONE": 100,
        "ERROR": -1,
    }
    return status_map.get(status, UPLOAD_PROGRESS)


def get_status_message(status: str) -> str:
    """
    Get user-friendly Japanese message for current processing status.

    Args:
        status: Current video status

    Returns:
        Japanese message describing the current processing step

    Examples:
        >>> get_status_message('STEP_3_TRANSCRIBE_AUDIO')
        '音声書き起こし中...'
        >>> get_status_message('DONE')
        '解析完了'
    """
    messages = {
        "NEW": "アップロード待ち",
        "uploaded": "アップロード完了",
        "STEP_0_EXTRACT_FRAMES": "フレーム抽出中...",
        "STEP_1_DETECT_PHASES": "フェーズ検出中...",
        "STEP_2_EXTRACT_METRICS": "メトリクス抽出中...",
        "STEP_3_TRANSCRIBE_AUDIO": "音声書き起こし中...",
        "STEP_4_IMAGE_CAPTION": "画像キャプション生成中...",
        "STEP_5_BUILD_PHASE_UNITS": "フェーズユニット構築中...",
        "STEP_6_BUILD_PHASE_DESCRIPTION": "フェーズ説明生成中...",
        "STEP_7_GROUPING": "グルーピング中...",
        "STEP_8_UPDATE_BEST_PHASE": "ベストフェーズ更新中...",
        "STEP_9_BUILD_VIDEO_STRUCTURE_FEATURES": "ビデオ構造特徴構築中...",
        "STEP_10_ASSIGN_VIDEO_STRUCTURE_GROUP": "ビデオ構造グループ割り当て中...",
        "STEP_11_UPDATE_VIDEO_STRUCTURE_GROUP_STATS": "ビデオ構造グループ統計更新中...",
        "STEP_12_UPDATE_VIDEO_STRUCTURE_BEST": "ビデオ構造ベスト更新中...",
        "STEP_13_BUILD_REPORTS": "レポート生成中...",
        "STEP_14_SPLIT_VIDEO": "ビデオ分割中...",
        "DONE": "解析完了",
        "ERROR": "エラーが発生しました",
    }
    return messages.get(status, "処理中...")
