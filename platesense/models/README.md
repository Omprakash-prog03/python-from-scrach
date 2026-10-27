# Models Directory

PlateSense works out of the box with a classical computer-vision detector
(edge detection + morphology + aspect-ratio filtering) and, when available,
OpenCV's built-in Haar cascade. For better accuracy on real-world Indian
number plates we recommend also installing a YOLO detector.

## Recommended detector

Place a YOLOv5 / YOLOv8 weights file trained for number plates at:

```
models/license_plate_detector.pt
```

You can use an open-source plate detector such as:

- [keremberke/yolov5n-license-plate](https://github.com/keremberke/awesome-yolov8-models)
- Any YOLOv5/YOLOv8 weights exported to `.pt` whose class 0 is "license-plate".

The app automatically detects the file at launch and uses it when present.
You can also pick a custom weights file from **Settings → Detection → Model path**.

You will need the `ultralytics` package to use the YOLO backend:

```bash
pip install ultralytics
```

If no YOLO weights are present the application falls back to the classical
detector and still produces bounding-boxes — accuracy will be lower but the
pipeline works fully offline.

## OCR models

EasyOCR downloads its language models on first run. If you are on a restricted
network you can pre-place the files in `~/.EasyOCR/model/`:

- `craft_mlt_25k.pth` (text detector)
- `english_g2.pth` (English recognizer)

If EasyOCR is unavailable the app will still localize plates (bounding boxes
and crops) and ask you to install OCR to read the characters.
