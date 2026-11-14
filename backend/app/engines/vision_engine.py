
import io

import numpy as np
import torch
import open_clip

from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)


class VisionEngine:

    def __init__(self, model_name, pretrained):

        self.device = (
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        self.model, _, self.preprocess = (
            open_clip.create_model_and_transforms(
                model_name,
                pretrained=pretrained,
                device=self.device,
            )
        )

        self.model.eval()

        self.tokenizer = open_clip.get_tokenizer(
            model_name
        )

    def prepare_image(self, file_bytes):

        try:
            image = Image.open(
                io.BytesIO(file_bytes)
            )

            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")

            if image.width < 10 or image.height < 10:
                raise ValueError(
                    "Image dimensions are too small."
                )

            if image.width > 10000 or image.height > 10000:
                raise ValueError(
                    "Image dimensions are too large."
                )

            return image

        except (
            UnidentifiedImageError,
            OSError,
        ):
            raise ValueError(
                "Invalid or corrupted image."
            )

    @torch.inference_mode()
    def encode_image(self, file_bytes):

        image = self.prepare_image(file_bytes)

        tensor = self.preprocess(
            image
        ).unsqueeze(0)

        tensor = tensor.to(self.device)

        features = self.model.encode_image(tensor)

        features = features / features.norm(
            dim=-1,
            keepdim=True,
        )

        vector = features.cpu().numpy()[0]

        return vector.astype(
            np.float32
        ).tolist()

    @staticmethod
    def similarity(vector_a, vector_b):

        a = np.asarray(
            vector_a,
            dtype=np.float32,
        )

        b = np.asarray(
            vector_b,
            dtype=np.float32,
        )

        denominator = (
            np.linalg.norm(a) *
            np.linalg.norm(b)
        )

        if denominator == 0:
            return 0.0

        cosine = float(
            np.dot(a, b) / denominator
        )

        return round(
            max(0.0, min(1.0, cosine)) * 100,
            2,
        )
