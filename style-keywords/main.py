import os
import time
import glob
import cv2
import argparse

from capture import FrameCapture, frame_changed
from detector import PersonDetector
from analyzer import StyleAnalyzer, BACKEND
from storage import init_db, save_analysis, get_recent, DB_PATH

# ─────────────────────────────────────────────
# TIME INTERVAL — seconds between API calls
# Examples: 0.1 (every 100ms), 0.5, 1.0, 2.0
# ─────────────────────────────────────────────
ANALYSIS_INTERVAL = 2.0

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


def print_keywords(scores: dict, source_label: str = ""):
    label = f" ({source_label})" if source_label else ""
    scored = sorted(((k, v) for k, v in scores.items() if v > 0), key=lambda x: -x[1])
    print(f"\n--- Style Analysis{label} ---")
    for k, v in scored:
        bar = "█" * int(v * 10)
        print(f"  {k:<22} {v:.2f}  {bar}")
    print(f"  ({len(scored)} keywords scored)")
    print("----------------------")


def analyze_image(image_path: str, backend: str):
    """Analyze a single image file and print + save results."""
    if not os.path.isfile(image_path):
        print(f"[image] File not found: {image_path}")
        return

    frame = cv2.imread(image_path)
    if frame is None:
        print(f"[image] Could not read image: {image_path}")
        return

    init_db()
    detector = PersonDetector()
    analyzer = StyleAnalyzer(backend=backend)
    filename = os.path.basename(image_path)
    print(f"[image] analyzing {filename}  (backend={backend})")

    crops = detector.get_person_crops(frame)
    if not crops:
        print(f"[image] No person detected in {filename} — sending full image to model")
        crops = [frame]  # fall back to full image

    largest = max(crops, key=lambda c: c.shape[0] * c.shape[1])
    result = analyzer.analyze(largest)
    if result:
        import json as _json
        raw = _json.dumps(result)
        save_analysis(image_path, raw, result)
        scored_count = sum(1 for v in result.values() if v > 0)
        print(f"[OK] {filename} → analysed | {scored_count} keywords scored")
        print_keywords(result, source_label=filename)
    else:
        from storage import KEYWORDS as _KW
        import json as _json
        save_analysis(image_path, "", {k: 0.0 for k in _KW})
        print(f"[FAIL] {filename} → parse error, zeros written")


def analyze_image_folder(folder_path: str, backend: str):
    """Analyze all images in a folder."""
    if not os.path.isdir(folder_path):
        print(f"[folder] Not a directory: {folder_path}")
        return

    files = sorted([
        f for f in glob.glob(os.path.join(folder_path, "*"))
        if os.path.splitext(f)[1].lower() in SUPPORTED_IMAGE_EXTS
    ])

    if not files:
        print(f"[folder] No supported images found in {folder_path}")
        print(f"  Supported: {', '.join(SUPPORTED_IMAGE_EXTS)}")
        return

    print(f"[folder] Found {len(files)} image(s) — processing...")
    for i, path in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}]", end=" ")
        analyze_image(path, backend=backend)


def run(source: int | str, show_window: bool, backend: str = BACKEND, interval: float = ANALYSIS_INTERVAL):
    init_db()
    capture = FrameCapture(source)
    detector = PersonDetector()
    analyzer = StyleAnalyzer(backend=backend)
    print(f"[main] started — source={source}  backend={backend}  interval={interval}s  press Q to quit")

    prev_frame = None
    last_analysis_time = 0.0

    try:
        while True:
            frame = capture.read()
            if frame is None:
                print("[main] end of stream")
                break

            if show_window:
                cv2.imshow("Style Keywords", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            now = time.time()
            if now - last_analysis_time < interval:
                continue

            if not frame_changed(prev_frame, frame):
                continue

            crops = detector.get_person_crops(frame)
            if not crops:
                continue

            largest = max(crops, key=lambda c: c.shape[0] * c.shape[1])
            result = analyzer.analyze(largest)
            if result:
                import json as _json
                raw = _json.dumps(result)
                save_analysis(f"frame@{now:.2f}", raw, result)
                scored_count = sum(1 for v in result.values() if v > 0)
                print(f"[OK] frame@{now:.2f} → analysed | {scored_count} keywords scored")
                print_keywords(result)
                prev_frame = frame.copy()
                last_analysis_time = now

    finally:
        capture.release()
        if show_window:
            cv2.destroyAllWindows()


def show_history(limit: int = 20):
    rows = get_recent(limit)
    if not rows:
        print("No results yet.")
        return
    print(f"\n{'#':<5} {'Analysed at':<22} {'KWs':<5} {'Top keywords'}")
    print("-" * 80)
    for r in rows:
        top = ", ".join(f"{k}({v:.1f})" for k, v in r["top_keywords"])
        src = os.path.basename(r["image_path"])
        print(f"{r['id']:<5} {r['analysed_at'][:19]:<22} {r['keyword_count']:<5} {top}  [{src}]")
    print(f"\nDatabase: {os.path.abspath(DB_PATH)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Style keyword extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py                                    # webcam
  python main.py --source 1                         # second camera
  python main.py --video /path/to/video.mp4         # video file
  python main.py --image /path/to/photo.jpg         # single image
  python main.py --image-folder /path/to/photos/    # all images in folder
  python main.py --interval 1.0                     # analyze every 1 second
  python main.py --history                          # show saved results
        """
    )
    parser.add_argument("--source",       default="0",   help="Camera index (default: 0)")
    parser.add_argument("--video",        default=None,  help="Path to a video file (.mp4 .mov .avi ...)")
    parser.add_argument("--image",        default=None,  help="Path to a single image file (.jpg .png ...)")
    parser.add_argument("--image-folder", default=None,  help="Path to a folder — analyzes all images inside")
    parser.add_argument("--interval",     default=ANALYSIS_INTERVAL, type=float,
                                                         help=f"Seconds between API calls (default: {ANALYSIS_INTERVAL})")
    parser.add_argument("--no-window",    action="store_true", help="Disable preview window (headless)")
    parser.add_argument("--history",      action="store_true", help="Print recent observations and exit")
    parser.add_argument("--backend",      default=BACKEND, choices=["claude", "gemini", "ollama"],
                                                         help=f"Vision backend (default: {BACKEND})")
    args = parser.parse_args()

    if args.history:
        show_history()
    elif args.image:
        analyze_image(args.image, backend=args.backend)
    elif args.image_folder:
        analyze_image_folder(args.image_folder, backend=args.backend)
    else:
        if args.video:
            source = args.video
        else:
            source = int(args.source) if args.source.isdigit() else args.source
        run(source, show_window=not args.no_window, backend=args.backend, interval=args.interval)
