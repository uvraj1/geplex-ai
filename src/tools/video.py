"""Video generation tool backed by OpenAI-compatible video endpoints."""

import asyncio
import json
from pathlib import Path

from src.tools._common import _parse_tool_args


async def do_generate_video(content: str, session_id=None, owner=None):
    """Create a video from a prompt and return a local playable URL.

    JSON args: prompt, model (optional), seconds (optional), size (optional).
    The provider must expose POST /videos and GET /videos/{id}/content.
    """
    import httpx
    from src.ai_interaction import _resolve_model
    from src.constants import GENERATED_IMAGES_DIR

    try:
        args = _parse_tool_args(content)
    except ValueError:
        return {"error": "Invalid JSON arguments", "exit_code": 1}
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return {"error": "Video prompt is required", "exit_code": 1}
    model_name = str(args.get("model") or "").strip()
    try:
        url, model_id, headers = await asyncio.to_thread(
            _resolve_model, model_name, owner=owner, model_type="video"
        )
    except (TypeError, ValueError):
        return {
            "error": "No video model found. Configure a video endpoint in Settings or Cookbook.",
            "exit_code": 1,
        }

    base = url.replace("/chat/completions", "").rstrip("/")
    payload = {
        "model": model_id,
        "prompt": prompt,
        "seconds": str(args.get("seconds") or "5"),
        "size": str(args.get("size") or "1280x720"),
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=900)) as client:
            response = await client.post(f"{base}/videos", json=payload, headers=headers)
            response.raise_for_status()
            job = response.json()
            video_id = job.get("id")
            if not video_id:
                return {"error": "Video provider did not return a job id", "exit_code": 1}
            for _ in range(180):
                status = await client.get(f"{base}/videos/{video_id}", headers=headers)
                status.raise_for_status()
                state = status.json()
                if state.get("status") in {"completed", "succeeded"}:
                    break
                if state.get("status") in {"failed", "cancelled"}:
                    return {"error": state.get("error") or "Video generation failed", "exit_code": 1}
                await asyncio.sleep(5)
            else:
                return {"error": "Video generation timed out", "exit_code": 1}
            media = await client.get(f"{base}/videos/{video_id}/content", headers=headers)
            media.raise_for_status()

        directory = Path(GENERATED_IMAGES_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{video_id}.mp4"
        (directory / filename).write_bytes(media.content)
        return {
            "output": f"Video generated: {filename}",
            "video_url": f"/api/generated-image/{filename}",
            "video_id": video_id,
            "video_prompt": prompt,
            "video_model": model_id,
            "exit_code": 0,
        }
    except httpx.HTTPError as exc:
        return {"error": f"Video generation request failed: {exc}", "exit_code": 1}
