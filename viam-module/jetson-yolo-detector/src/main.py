#!/usr/bin/env python3
import asyncio
from viam.module.module import Module
from models.yolo_tensorrt import YoloTensorrt as YoloTensorrtModel


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
