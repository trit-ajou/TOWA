#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import re
import subprocess
import sys
from pathlib import Path
import unicodedata
from typing import Any


@dataclass(frozen=True)
class ScriptCaption:
    id: str
    text: str


@dataclass(frozen=True)
class SttUnit:
    text: str
    start_sec: float
    end_sec: float


@dataclass(frozen=True)
class TimedCaption:
    id: str
    text: str
    start_sec: float
    end_sec: float
    similarity: float
    stt_text: str
    skipped_stt: list[str]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="presentation_subtitles",
        description="Build synced subtitles for a single TOWA presentation recording.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="extract audio, transcribe, align, write subtitles, and optionally burn in")
    _add_common_run_args(run)
    run.set_defaults(func=_run_pipeline)

    extract = subcommands.add_parser("extract-audio", help="extract mono 16 kHz wav audio from a video")
    extract.add_argument("--video", required=True)
    extract.add_argument("--audio", required=True)
    extract.set_defaults(func=_extract_audio_command)

    transcribe = subcommands.add_parser("transcribe", help="transcribe an extracted wav file with faster-whisper")
    transcribe.add_argument("--audio", required=True)
    transcribe.add_argument("--out", required=True)
    transcribe.add_argument("--model", default="small")
    transcribe.add_argument("--language", default="ko")
    transcribe.add_argument("--device", default="cpu")
    transcribe.add_argument("--compute-type", default="int8")
    transcribe.set_defaults(func=_transcribe_command)

    align = subcommands.add_parser("align", help="align a plain spoken script with stt.json")
    align.add_argument("--script", required=True)
    align.add_argument("--stt", required=True)
    align.add_argument("--out", required=True)
    align.add_argument("--max-caption-chars", type=int, default=34)
    align.add_argument("--min-similarity", type=float, default=0.42)
    align.add_argument("--max-window-units", type=int, default=36)
    align.add_argument("--max-skip-units", type=int, default=8)
    align.add_argument("--caption-tail-sec", type=float, default=0.35)
    align.add_argument("--subtitle-offset-sec", type=float, default=0.0)
    align.set_defaults(func=_align_command)

    write_subtitles = subcommands.add_parser("write-subtitles", help="write SRT and ASS files from alignment.json")
    write_subtitles.add_argument("--alignment", required=True)
    write_subtitles.add_argument("--srt", required=True)
    write_subtitles.add_argument("--ass", required=True)
    write_subtitles.set_defaults(func=_write_subtitles_command)

    burn = subcommands.add_parser("burn-in", help="burn an ASS subtitle file into the source video")
    burn.add_argument("--video", required=True)
    burn.add_argument("--ass", required=True)
    burn.add_argument("--out", required=True)
    burn.add_argument("--font-dir", default="presentation/towa-softcon/assets/fonts")
    burn.set_defaults(func=_burn_in_command)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


def _add_common_run_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--video", required=True, help="repo-relative path to the presentation recording")
    parser.add_argument("--script", required=True, help="repo-relative path to the plain spoken script")
    parser.add_argument("--out-dir", required=True, help="directory for generated audio, STT, subtitles, and video")
    parser.add_argument("--model", default="small", help="faster-whisper model name")
    parser.add_argument("--language", default="ko")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--max-caption-chars", type=int, default=34)
    parser.add_argument("--min-similarity", type=float, default=0.42)
    parser.add_argument("--max-window-units", type=int, default=36)
    parser.add_argument("--max-skip-units", type=int, default=8)
    parser.add_argument("--caption-tail-sec", type=float, default=0.35)
    parser.add_argument("--subtitle-offset-sec", type=float, default=0.0)
    parser.add_argument("--font-dir", default="presentation/towa-softcon/assets/fonts")
    parser.add_argument("--burn-in", action="store_true", help="also write subtitled.mp4")


def _run_pipeline(args: argparse.Namespace) -> int:
    video = _existing_file(args.video, "video")
    script = _existing_file(args.script, "script")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    audio = out_dir / "audio.wav"
    stt_path = out_dir / "stt.json"
    alignment_path = out_dir / "alignment.json"
    srt_path = out_dir / "subtitles.srt"
    ass_path = out_dir / "subtitles.ass"
    output_video = out_dir / "subtitled.mp4"

    print(f"[1/5] Extracting audio: {audio}")
    extract_audio(video, audio)

    print(f"[2/5] Transcribing audio with faster-whisper: {stt_path}")
    stt = transcribe_audio(
        audio,
        model_name=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
    )
    _write_json(stt_path, stt)

    print(f"[3/5] Aligning script to STT: {alignment_path}")
    timed = align_script_to_stt(
        script,
        stt,
        max_caption_chars=args.max_caption_chars,
        min_similarity=args.min_similarity,
        max_window_units=args.max_window_units,
        max_skip_units=args.max_skip_units,
        caption_tail_sec=args.caption_tail_sec,
        subtitle_offset_sec=args.subtitle_offset_sec,
    )
    _write_json(alignment_path, {"captions": [_timed_caption_dict(caption) for caption in timed]})

    print(f"[4/5] Writing subtitles: {srt_path}, {ass_path}")
    write_srt(timed, srt_path)
    write_ass(timed, ass_path)

    if args.burn_in:
        print(f"[5/5] Burning subtitles into video: {output_video}")
        burn_subtitles(video, ass_path, output_video, font_dir=_existing_dir(args.font_dir, "font-dir"))
    else:
        print("[5/5] Burn-in skipped. Pass --burn-in to create subtitled.mp4.")

    print("Done.")
    return 0


def _extract_audio_command(args: argparse.Namespace) -> int:
    extract_audio(_existing_file(args.video, "video"), Path(args.audio))
    print(f"Wrote {args.audio}")
    return 0


def _transcribe_command(args: argparse.Namespace) -> int:
    stt = transcribe_audio(
        _existing_file(args.audio, "audio"),
        model_name=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
    )
    _write_json(Path(args.out), stt)
    print(f"Wrote {args.out}")
    return 0


def _align_command(args: argparse.Namespace) -> int:
    stt = _read_json(_existing_file(args.stt, "stt"))
    timed = align_script_to_stt(
        _existing_file(args.script, "script"),
        stt,
        max_caption_chars=args.max_caption_chars,
        min_similarity=args.min_similarity,
        max_window_units=args.max_window_units,
        max_skip_units=args.max_skip_units,
        caption_tail_sec=args.caption_tail_sec,
        subtitle_offset_sec=args.subtitle_offset_sec,
    )
    _write_json(Path(args.out), {"captions": [_timed_caption_dict(caption) for caption in timed]})
    print(f"Wrote {args.out}")
    return 0


def _burn_in_command(args: argparse.Namespace) -> int:
    burn_subtitles(
        _existing_file(args.video, "video"),
        _existing_file(args.ass, "ass"),
        Path(args.out),
        font_dir=_existing_dir(args.font_dir, "font-dir"),
    )
    print(f"Wrote {args.out}")
    return 0


def _write_subtitles_command(args: argparse.Namespace) -> int:
    payload = _read_json(_existing_file(args.alignment, "alignment"))
    captions = [_timed_caption_from_dict(item) for item in _required_caption_items(payload)]
    write_srt(captions, Path(args.srt))
    write_ass(captions, Path(args.ass))
    print(f"Wrote {args.srt}")
    print(f"Wrote {args.ass}")
    return 0


def extract_audio(video: Path, audio: Path) -> None:
    audio.parent.mkdir(parents=True, exist_ok=True)
    _run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio),
        ]
    )


def transcribe_audio(
    audio: Path,
    *,
    model_name: str,
    language: str,
    device: str,
    compute_type: str,
) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is required. Run this command through docker compose.") from exc

    try:
        from tqdm import tqdm
    except ImportError as exc:
        raise RuntimeError("tqdm is required. Run this command through docker compose.") from exc

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        str(audio),
        language=language,
        word_timestamps=True,
        vad_filter=False,
    )

    output_segments: list[dict[str, Any]] = []
    for index, segment in enumerate(tqdm(segments, desc="STT segments", unit="segment"), start=1):
        words = [
            {
                "text": str(word.word).strip(),
                "start_sec": round(float(word.start), 3),
                "end_sec": round(float(word.end), 3),
            }
            for word in (segment.words or [])
            if str(word.word).strip()
        ]
        output_segments.append(
            {
                "id": f"stt_segment_{index}",
                "text": str(segment.text).strip(),
                "start_sec": round(float(segment.start), 3),
                "end_sec": round(float(segment.end), 3),
                "words": words,
            }
        )

    return {
        "provider": "faster_whisper",
        "model": model_name,
        "language": getattr(info, "language", language),
        "segments": output_segments,
    }


def align_script_to_stt(
    script_path: Path,
    stt: dict[str, Any],
    *,
    max_caption_chars: int,
    min_similarity: float,
    max_window_units: int,
    max_skip_units: int,
    caption_tail_sec: float,
    subtitle_offset_sec: float,
) -> list[TimedCaption]:
    captions = load_script_captions(script_path, max_caption_chars=max_caption_chars)
    units = transcription_units(stt)
    if not captions:
        raise ValueError("script must contain at least one spoken line.")
    if not units:
        raise ValueError("stt.json must include at least one timestamped segment or word.")

    cursor = 0
    timed: list[TimedCaption] = []
    for caption in captions:
        match = best_ordered_match(
            caption.text,
            units,
            cursor,
            min_similarity=min_similarity,
            max_window_units=max_window_units,
            max_skip_units=max_skip_units,
            caption_id=caption.id,
        )
        skipped = [unit.text for unit in units[cursor : match["start_cursor"]]]
        timed.append(
            TimedCaption(
                id=caption.id,
                text=caption.text,
                start_sec=round(match["start_sec"] + subtitle_offset_sec, 3),
                end_sec=round(match["end_sec"] + subtitle_offset_sec + caption_tail_sec, 3),
                similarity=round(match["similarity"], 4),
                stt_text=match["stt_text"],
                skipped_stt=skipped,
            )
        )
        cursor = match["next_cursor"]
    return clamp_caption_timing(timed)


def load_script_captions(script_path: Path, *, max_caption_chars: int) -> list[ScriptCaption]:
    lines = [line.strip() for line in script_path.read_text(encoding="utf-8").splitlines()]
    spoken_lines = [line for line in lines if line]
    captions: list[ScriptCaption] = []
    for line in spoken_lines:
        for text in split_caption_text(line, max_caption_chars=max_caption_chars):
            captions.append(ScriptCaption(id=f"caption_{len(captions) + 1:04d}", text=text))
    return captions


def split_caption_text(text: str, *, max_caption_chars: int) -> list[str]:
    if max_caption_chars < 12:
        raise ValueError("max_caption_chars must be at least 12.")
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []

    sentence_chunks = _sentence_chunks(normalized)
    result: list[str] = []
    for chunk in sentence_chunks:
        result.extend(_wrap_caption_chunk(chunk, max_caption_chars=max_caption_chars))
    return result


def _sentence_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    for index, char in enumerate(text):
        if char in ".!?。！？…":
            chunk = text[start : index + 1].strip()
            if chunk:
                chunks.append(chunk)
            start = index + 1
    tail = text[start:].strip()
    if tail:
        chunks.append(tail)
    return chunks or [text]


def _wrap_caption_chunk(text: str, *, max_caption_chars: int) -> list[str]:
    if len(text) <= max_caption_chars:
        return [text]

    words = text.split()
    if len(words) == 1:
        return [text[index : index + max_caption_chars] for index in range(0, len(text), max_caption_chars)]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_caption_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def transcription_units(stt: dict[str, Any]) -> list[SttUnit]:
    units: list[SttUnit] = []
    raw_segments = stt.get("segments", [])
    if not isinstance(raw_segments, list):
        raise ValueError("stt.json segments must be an array.")

    for segment in raw_segments:
        if not isinstance(segment, dict):
            raise ValueError("stt.json segments must contain objects.")
        words = segment.get("words")
        if isinstance(words, list) and words and not _has_zero_duration_word(words):
            for word in words:
                if isinstance(word, dict):
                    units.append(_unit_from(word))
        else:
            units.append(_unit_from(segment))
    return units


def _has_zero_duration_word(words: list[Any]) -> bool:
    for word in words:
        if not isinstance(word, dict):
            continue
        start = word.get("start_sec")
        end = word.get("end_sec")
        if isinstance(start, bool) or isinstance(end, bool):
            continue
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and float(end) == float(start):
            return True
    return False


def _unit_from(source: dict[str, Any]) -> SttUnit:
    text = str(source.get("text", "")).strip()
    start = source.get("start_sec")
    end = source.get("end_sec")
    if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        raise ValueError("STT units must include numeric start_sec and end_sec.")
    if not text or float(end) <= float(start):
        raise ValueError("STT units must include non-empty text and positive duration.")
    return SttUnit(text=text, start_sec=float(start), end_sec=float(end))


def best_ordered_match(
    text: str,
    units: list[SttUnit],
    cursor: int,
    *,
    min_similarity: float,
    max_window_units: int,
    max_skip_units: int,
    caption_id: str,
) -> dict[str, Any]:
    target = content_key(text)
    if not target:
        raise ValueError(f"{caption_id} has no alignable text.")

    best: dict[str, Any] | None = None
    max_start = min(len(units), cursor + max_skip_units + 1)
    for start_index in range(cursor, max_start):
        max_end = min(len(units), start_index + max_window_units)
        for end_index in range(start_index, max_end):
            candidate_units = units[start_index : end_index + 1]
            stt_text = "".join(unit.text for unit in candidate_units)
            candidate = content_key(stt_text)
            similarity = SequenceMatcher(None, target, candidate).ratio()
            if best is None or similarity > best["similarity"]:
                best = {
                    "similarity": similarity,
                    "start_sec": round(units[start_index].start_sec, 3),
                    "end_sec": round(units[end_index].end_sec, 3),
                    "start_cursor": start_index,
                    "next_cursor": end_index + 1,
                    "stt_text": stt_text,
                }
            if similarity >= 0.985:
                break

    if best is None or best["similarity"] < min_similarity:
        similarity = 0.0 if best is None else best["similarity"]
        raise ValueError(
            f"Could not align {caption_id}: text={text!r}; best_similarity={similarity:.3f}; "
            f"min_similarity={min_similarity:.3f}"
        )
    return best


def content_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return "".join(char for char in normalized if _is_content_char(char))


def _is_content_char(char: str) -> bool:
    category = unicodedata.category(char)
    return category[0] in {"L", "N"}


def clamp_caption_timing(captions: list[TimedCaption]) -> list[TimedCaption]:
    clamped: list[TimedCaption] = []
    for index, caption in enumerate(captions):
        start = max(0.0, caption.start_sec)
        end = max(start + 0.35, caption.end_sec)
        if index + 1 < len(captions):
            next_start = max(0.0, captions[index + 1].start_sec)
            if end >= next_start:
                end = max(start + 0.35, next_start - 0.04)
        clamped.append(
            TimedCaption(
                id=caption.id,
                text=caption.text,
                start_sec=round(start, 3),
                end_sec=round(end, 3),
                similarity=caption.similarity,
                stt_text=caption.stt_text,
                skipped_stt=caption.skipped_stt,
            )
        )
    return clamped


def write_srt(captions: list[TimedCaption], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for index, caption in enumerate(captions, start=1):
        lines.append(str(index))
        lines.append(f"{srt_timestamp(caption.start_sec)} --> {srt_timestamp(caption.end_sec)}")
        lines.append(caption.text)
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_ass(captions: list[TimedCaption], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Gmarket Sans TTF Medium,56,&H00FFFFFF,&H000000FF,&H00111111,&H99000000,-1,0,0,0,100,100,0,0,1,3,0,2,90,90,70,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = [
        f"Dialogue: 0,{ass_timestamp(caption.start_sec)},{ass_timestamp(caption.end_sec)},Default,,0,0,0,,{escape_ass(caption.text)}"
        for caption in captions
    ]
    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def burn_subtitles(video: Path, ass_path: Path, output_video: Path, *, font_dir: Path) -> None:
    output_video.parent.mkdir(parents=True, exist_ok=True)
    subtitle_filter = f"subtitles='{_ffmpeg_filter_path(ass_path)}':fontsdir='{_ffmpeg_filter_path(font_dir)}'"
    _run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-vf",
            subtitle_filter,
            "-c:a",
            "copy",
            str(output_video),
        ]
    )


def srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def ass_timestamp(seconds: float) -> str:
    centis = int(round(seconds * 100))
    hours, remainder = divmod(centis, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centis:02d}"


def escape_ass(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def _ffmpeg_filter_path(path: Path) -> str:
    value = str(path)
    if "'" in value:
        raise ValueError(f"ffmpeg subtitle filter paths must not contain single quotes: {path}")
    return value.replace("\\", "/")


def _timed_caption_dict(caption: TimedCaption) -> dict[str, Any]:
    return {
        "id": caption.id,
        "text": caption.text,
        "start_sec": caption.start_sec,
        "end_sec": caption.end_sec,
        "similarity": caption.similarity,
        "matched_stt_text": caption.stt_text,
        "skipped_stt": caption.skipped_stt,
    }


def _timed_caption_from_dict(payload: dict[str, Any]) -> TimedCaption:
    return TimedCaption(
        id=_required_string(payload, "id"),
        text=_required_string(payload, "text"),
        start_sec=_required_number(payload, "start_sec"),
        end_sec=_required_number(payload, "end_sec"),
        similarity=_required_number(payload, "similarity"),
        stt_text=str(payload.get("matched_stt_text", "")),
        skipped_stt=[str(item) for item in payload.get("skipped_stt", [])],
    )


def _required_caption_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    captions = payload.get("captions")
    if not isinstance(captions, list) or not captions:
        raise ValueError("alignment JSON must include a non-empty captions array.")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(captions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"alignment captions[{index}] must be an object.")
        result.append(item)
    return result


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _required_number(payload: dict[str, Any], field: str) -> float:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric.")
    return float(value)


def _run_command(command: list[str]) -> None:
    print("+ " + " ".join(command))
    subprocess.run(command, check=True)


def _existing_file(value: str, label: str) -> Path:
    path = Path(value)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"{label} file not found: {path}")
    return path


def _existing_dir(value: str, label: str) -> Path:
    path = Path(value)
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"{label} directory not found: {path}")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}: {' '.join(exc.cmd)}", file=sys.stderr)
        raise SystemExit(exc.returncode)
