from __future__ import annotations

"""OCR 服务，优先使用 PaddleOCR，无法使用时自动回退到 pytesseract。"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

try:  # pragma: no cover - 测试环境可能缺少 PyMuPDF
    import fitz  # type: ignore
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

try:  # pragma: no cover - 轻量 PDF 文本读取
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore

logger = logging.getLogger(__name__)

try:  # pragma: no cover
    import pytesseract  # type: ignore
    from PIL import Image
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore


@dataclass
class OcrBlock:
    page: int
    bbox: List[float]
    text: str


class OcrService:
    """封装 OCR 逻辑，包括 PDF 页面渲染与图片识别。"""

    def __init__(self, use_gpu: bool = False, fallback: str = "pytesseract") -> None:
        self.use_gpu = use_gpu
        self.fallback = fallback
        self._paddle = None
        try:  # pragma: no cover - PaddleOCR 依赖较多
            from paddleocr import PaddleOCR  # type: ignore

            logger.info("初始化 PaddleOCR use_gpu=%s", use_gpu)
            self._paddle = PaddleOCR(use_angle_cls=True, lang="ch", use_gpu=use_gpu)
        except Exception as exc:  # pragma: no cover
            logger.warning("PaddleOCR 不可用，将使用 fallback: %s", exc)

    def _paddle_ocr(self, image_path: str) -> List[OcrBlock]:
        assert self._paddle is not None
        result = self._paddle.ocr(image_path, cls=True)
        blocks: List[OcrBlock] = []
        for idx, line in enumerate(result[0]):
            bbox = [float(v) for point in line[0] for v in point]
            text = line[1][0]
            blocks.append(OcrBlock(page=0, bbox=bbox, text=text))
        return blocks

    def _tesseract_ocr(self, image_path: str) -> List[OcrBlock]:
        if pytesseract is None or Image is None:
            raise RuntimeError("pytesseract 未安装，且 PaddleOCR 不可用")
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image, lang="chi_sim+eng")
        blocks = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                blocks.append(OcrBlock(page=0, bbox=[0, 0, 0, 0], text=line))
        return blocks

    def _pdf_to_images(self, pdf_path: str) -> Iterable[Path]:
        if fitz is None:  # pragma: no cover - 取决于外部依赖
            raise RuntimeError("PyMuPDF 未安装，无法将 PDF 渲染为图片")
        doc = fitz.open(pdf_path)
        output_dir = Path("data/tmp/pdf")
        output_dir.mkdir(parents=True, exist_ok=True)
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=150)
            image_path = output_dir / f"page_{page_index}.png"
            pix.save(image_path)
            yield image_path

    def run(self, file_path: str) -> List[OcrBlock]:
        logger.info("开始 OCR: %s", file_path)
        path = Path(file_path)
        blocks: List[OcrBlock] = []
        if path.suffix.lower() == ".pdf":
            if fitz is None:
                blocks.extend(self._extract_pdf_text(path))
            else:
                for page_index, image_path in enumerate(self._pdf_to_images(file_path)):
                    blocks.extend(self._recognize_image(str(image_path), page_index))
        else:
            blocks.extend(self._recognize_image(file_path, 0))
        return blocks

    def _recognize_image(self, image_path: str, page_index: int) -> List[OcrBlock]:
        if self._paddle is not None:
            result = self._paddle_ocr(image_path)
        elif pytesseract is not None and Image is not None:
            logger.info("使用 fallback OCR: %s", self.fallback)
            result = self._tesseract_ocr(image_path)
        else:
            logger.warning("未找到 OCR 引擎，将返回空结果，可在后续流程中使用 PDF 文本抽取替代。")
            result = []
        for block in result:
            block.page = page_index
        return result

    def _extract_pdf_text(self, pdf_path: Path) -> List[OcrBlock]:
        logger.info("直接读取 PDF 文本: %s", pdf_path)
        blocks: List[OcrBlock] = []
        if PdfReader is None:
            logger.warning("缺少 pypdf 依赖，返回空结果。")
            return blocks
        reader = PdfReader(str(pdf_path))
        for page_index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text:
                blocks.append(OcrBlock(page=page_index, bbox=[0, 0, 0, 0], text=text))
        return blocks


__all__ = ["OcrService", "OcrBlock"]
