"""
YoloTensorrt — Viam Vision Service Module
Implements get_detections() using a YOLO TensorRT engine on Jetson Orin Nano.

Configuration attributes (set in Viam app):
  model_path  (str, required) : Absolute path to best.engine on the Jetson
  confidence  (float, optional, default 0.5) : Detection confidence threshold
  labels      (list, optional) : Override class name list (e.g. ["tanmay", "other_person"])
"""

import numpy as np
from pathlib import Path
from typing import ClassVar, List, Mapping, Optional, Sequence, Tuple

from typing_extensions import Self
from viam.media.video import ViamImage
from viam.media.utils.pil import viam_to_pil_image
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import PointCloudObject, ResourceName
from viam.proto.service.vision import Classification, Detection, GetPropertiesResponse
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.services.vision import Vision, CaptureAllResult
from viam.utils import ValueTypes


class YoloTensorrt(Vision, EasyResource):
    MODEL: ClassVar[Model] = Model(
        ModelFamily("tanmay-bhatnagar", "jetson-yolo-detector"), "yolo-tensorrt"
    )

    # Runtime state — set in reconfigure()
    _yolo = None
    _confidence: float = 0.5
    _labels: Optional[List[str]] = None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        instance = super().new(config, dependencies)
        return instance

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        fields = config.attributes.fields
        if "model_path" not in fields:
            raise Exception(
                "model_path is required — set it to the absolute path of your "
                "best.engine file on the Jetson (e.g. /home/user/models/best.engine)"
            )
        model_path = fields["model_path"].string_value
        if not Path(model_path).exists():
            raise Exception(f"model_path does not exist: {model_path}")
        return [], []  # no resource dependencies

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> None:
        from ultralytics import YOLO

        fields = config.attributes.fields
        model_path = fields["model_path"].string_value
        self._confidence = (
            fields["confidence"].number_value if "confidence" in fields else 0.5
        )

        # Optional label override
        if "labels" in fields:
            self._labels = [
                v.string_value for v in fields["labels"].list_value.values
            ]
        else:
            self._labels = None

        self.logger.info(f"Loading YOLO engine from: {model_path}")
        self._yolo = YOLO(model_path)
        self.logger.info("YOLO engine loaded successfully ✓")

    async def close(self):
        self.logger.info("YoloTensorrt shutting down")
        self._yolo = None

    # -------------------------------------------------------------------------
    # Core Vision API — get_detections (the one that matters)
    # -------------------------------------------------------------------------

    async def get_detections(
        self,
        image: ViamImage,
        *,
        extra: Optional[Mapping[str, ValueTypes]] = None,
        timeout: Optional[float] = None,
    ) -> List[Detection]:
        if self._yolo is None:
            raise RuntimeError("Model not loaded — check module configuration")

        # Convert ViamImage → PIL → numpy (BGR for ultralytics)
        pil_img = viam_to_pil_image(image)
        frame = np.array(pil_img)  # RGB numpy array — ultralytics handles both

        results = self._yolo(frame, conf=self._confidence, stream=False, verbose=False)

        detections: List[Detection] = []
        for r in results:
            if r.boxes is None:
                continue
            names = self._labels if self._labels else r.names
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                label = names[cls_id] if isinstance(names, list) else names.get(cls_id, str(cls_id))
                detections.append(
                    Detection(
                        x_min=x1, y_min=y1, x_max=x2, y_max=y2,
                        confidence=conf,
                        class_name=label,
                    )
                )

        return detections

    async def get_detections_from_camera(
        self,
        camera_name: str,
        *,
        extra: Optional[Mapping[str, ValueTypes]] = None,
        timeout: Optional[float] = None,
    ) -> List[Detection]:
        """Convenience wrapper — Viam fetches the frame and calls get_detections."""
        raise NotImplementedError(
            "Use get_detections() directly with a camera image, or configure a "
            "camera component and use capture_all_from_camera()."
        )

    # -------------------------------------------------------------------------
    # Properties — tell Viam what this service supports
    # -------------------------------------------------------------------------

    async def get_properties(
        self,
        *,
        extra: Optional[Mapping[str, ValueTypes]] = None,
        timeout: Optional[float] = None,
    ) -> Vision.Properties:
        return Vision.Properties(
            classifications_supported=False,
            detections_supported=True,
            object_point_clouds_supported=False,
        )

    # -------------------------------------------------------------------------
    # Unimplemented (not needed for a detector)
    # -------------------------------------------------------------------------

    async def capture_all_from_camera(self, camera_name, return_image=False,
        return_classifications=False, return_detections=False,
        return_object_point_clouds=False, *, extra=None, timeout=None) -> CaptureAllResult:
        raise NotImplementedError()

    async def get_classifications_from_camera(self, camera_name, count, *, extra=None, timeout=None):
        raise NotImplementedError()

    async def get_classifications(self, image, count, *, extra=None, timeout=None):
        raise NotImplementedError()

    async def get_object_point_clouds(self, camera_name, *, extra=None, timeout=None):
        raise NotImplementedError()

    async def do_command(self, command, *, timeout=None, **kwargs):
        raise NotImplementedError()

    async def get_status(self, *, timeout=None, **kwargs):
        raise NotImplementedError()
