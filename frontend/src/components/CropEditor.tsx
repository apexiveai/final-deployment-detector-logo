
import { useCallback, useEffect, useState } from "react";
import Cropper, { type Area, type Point } from "react-easy-crop";
import "./CropEditor.css";

async function createCroppedImage(
  imageSrc: string,
  pixels: Area,
  rotation: number
): Promise<Blob> {
  const image = new Image();

  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error("Unable to load image."));
    image.src = imageSrc;
  });

  const radians = (rotation * Math.PI) / 180;

  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Unable to prepare image canvas.");

  const width = Math.round(
    Math.abs(image.width * Math.cos(radians)) +
    Math.abs(image.height * Math.sin(radians))
  );

  const height = Math.round(
    Math.abs(image.width * Math.sin(radians)) +
    Math.abs(image.height * Math.cos(radians))
  );

  canvas.width = width;
  canvas.height = height;

  context.translate(width / 2, height / 2);
  context.rotate(radians);
  context.drawImage(
    image,
    -image.width / 2,
    -image.height / 2
  );

  const croppedCanvas = document.createElement("canvas");
  const croppedContext = croppedCanvas.getContext("2d");
  if (!croppedContext) throw new Error("Unable to prepare crop canvas.");

  croppedCanvas.width = pixels.width;
  croppedCanvas.height = pixels.height;

  croppedContext.drawImage(
    canvas,
    pixels.x,
    pixels.y,
    pixels.width,
    pixels.height,
    0,
    0,
    pixels.width,
    pixels.height
  );

  return new Promise<Blob>((resolve, reject) => {
    croppedCanvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("Image crop failed."));
          return;
        }

        resolve(blob);
      },
      "image/png",
      0.95
    );
  });
}

type CropEditorProps = {
  file: File;
  onCancel: () => void;
  onApply: (file: File) => void;
};

export default function CropEditor({
  file,
  onCancel,
  onApply,
}: CropEditorProps) {
  const [image, setImage] = useState("");
  const [crop, setCrop] = useState<Point>({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [aspect, setAspect] = useState<number | null>(null);
  const [cropPixels, setCropPixels] = useState<Area | null>(null);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setImage(url);

    return () => URL.revokeObjectURL(url);
  }, [file]);

  const onCropComplete = useCallback(
    (_croppedArea: Area, croppedPixels: Area) => {
      setCropPixels(croppedPixels);
    },
    []
  );

  function resetEditor() {
    setCrop({ x: 0, y: 0 });
    setZoom(1);
    setRotation(0);
    setAspect(null);
  }

  async function applyCrop() {
    if (!cropPixels || processing) return;

    try {
      setProcessing(true);

      const blob = await createCroppedImage(
        image,
        cropPixels,
        rotation
      );

      const croppedFile = new File(
        [blob],
        `apexiveai-cropped-${file.name.replace(/\.[^.]+$/, "")}.png`,
        { type: "image/png" }
      );

      onApply(croppedFile);
    } catch (error) {
      console.error(error);
      alert("Unable to crop this image. Please try again.");
    } finally {
      setProcessing(false);
    }
  }

  return (
    <div
      className="crop-modal-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onCancel();
        }
      }}
    >
      <section className="crop-modal">
        <header className="crop-header">
          <div>
            <span className="crop-eyebrow">IMAGE PROCESSING</span>
            <h2>Adjust your trademark</h2>
            <p>Position and refine your image before analysis.</p>
          </div>

          <button
            className="crop-close"
            onClick={onCancel}
            aria-label="Close crop editor"
          >
            ×
          </button>
        </header>

        <div className="crop-workspace">
          {image && (
            <Cropper
              image={image}
              crop={crop}
              zoom={zoom}
              rotation={rotation}
              aspect={aspect || undefined}
              onCropChange={setCrop}
              onZoomChange={setZoom}
              onRotationChange={setRotation}
              onCropComplete={onCropComplete}
              restrictPosition={false}
            />
          )}
        </div>

        <div className="crop-controls">
          <div className="crop-control-group">
            <label>ASPECT RATIO</label>
            <div className="aspect-options">
              {[
                { label: "Free", value: null },
                { label: "1:1", value: 1 },
                { label: "4:3", value: 4 / 3 },
                { label: "16:9", value: 16 / 9 },
              ].map((option) => (
                <button
                  key={option.label}
                  className={
                    aspect === option.value ? "selected" : ""
                  }
                  onClick={() => setAspect(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="crop-control-group">
            <label>ZOOM · {zoom.toFixed(1)}×</label>
            <input
              type="range"
              min="1"
              max="3"
              step="0.1"
              value={zoom}
              onChange={(event) =>
                setZoom(Number(event.target.value))
              }
            />
          </div>

          <div className="crop-control-group">
            <label>ROTATION · {rotation}°</label>
            <div className="rotation-options">
              <button
                onClick={() =>
                  setRotation((value) => value - 90)
                }
              >
                ↶ Rotate Left
              </button>

              <button
                onClick={() =>
                  setRotation((value) => value + 90)
                }
              >
                ↷ Rotate Right
              </button>

              <button onClick={resetEditor}>
                Reset
              </button>
            </div>
          </div>
        </div>

        <footer className="crop-footer">
          <button
            className="crop-cancel"
            onClick={onCancel}
            disabled={processing}
          >
            Cancel
          </button>

          <button
            className="crop-apply"
            onClick={applyCrop}
            disabled={!cropPixels || processing}
          >
            {processing ? "Processing..." : "Apply Crop →"}
          </button>
        </footer>
      </section>
    </div>
  );
}
