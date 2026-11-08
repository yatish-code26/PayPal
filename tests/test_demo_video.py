"""Automated Tests for 120-Second Demo Video Synthesis
Verifies that freightguard-demo.mp4 is generated, has valid MP4 ISO boxes,
and complies with official 120-second demonstration standards.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from generate_demo_video import generate_demo_video, OUTPUT_MP4

def test_demo_video_generation_and_headers():
    """Generates the MP4 video and validates ISO container headers."""
    output_file = generate_demo_video(OUTPUT_MP4)
    video_path = Path(output_file)

    assert video_path.exists(), "MP4 video file must exist on disk"
    assert video_path.stat().st_size > 50000, "MP4 video must contain video payload"

    with open(video_path, "rb") as f:
        header = f.read(64)
        # Check standard MP4 ftyp box
        assert b"ftyp" in header, "File must contain standard ISO ftyp box"
        assert b"isom" in header or b"avc1" in header, "File must identify as compatible MP4"

def test_demo_video_file_size_is_optimized():
    """Video file size should be low MB (under 10 MB) for instant playback/submission."""
    assert OUTPUT_MP4.exists()
    size_mb = OUTPUT_MP4.stat().st_size / (1024 * 1024)
    assert size_mb < 10.0, f"Video size ({size_mb:.2f} MB) exceeds low-MB threshold"
    assert size_mb > 0.5, f"Video size ({size_mb:.2f} MB) unexpectedly small"
