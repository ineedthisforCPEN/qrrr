"""qrrr.py

Generate animated QR codes.
"""
import argparse
import itertools
import os.path
import PIL
import qrcode

from ecc import (DENSITY, ECC_MAP, ECC_MODES)


MAX_FPS = 20
MAX_VERSION = len(DENSITY[0])


class QrrrFrameFactory(object):
    """QrrrFrameFactory

    Provides a mechanism to reliably create one or more frames of a Qrrr
    code.
    """
    def __init__(self, qr: qrcode.QRCode) -> None:
        """Constructor for QrrrFrameFactory

        Parameters:
            qr  QR code object used as a base for all QRRR frames.
        """
        self.qr = qr
        self.chunk_size = DENSITY[qr.error_correction][qr._version - 1]

    def _get_progressbar_image(self, progress: float) -> PIL.Image:
        """Create the progress bar component of a QRRR frame.

        Parameters:
            progress    Progress of the generated frame (1.0 for 100%)

        Returns:
            Returns a PIL.Image object with the progress bar drawn.
            There is padding on the left, right, and bottom edged of the
            image but not on the top.
        """
        # The progress bar will be appended to the bottom of the animated QR
        # code and will show how far along the animated QR code is. The progress
        # bar should have borders around the left, right, and bottom edges. The
        # border on the top edge of the progress bar will be shared by the
        # border of the bottom of the QR code.

        # Let's start by determining how large the progress bar should be in
        # terms of QR code "pixels" (or boxes).
        im_width = 4 * self.qr._version + 2 * self.qr.border + 17
        im_height = max(2, (4 * self.qr._version) // 10) + self.qr.border

        bar_width = int(progress * (im_width - 2 * self.qr.border))
        bar_height = im_height - self.qr.border

        # Determine where the progress bar should be drawn by finding the top-
        # left (x0, y0) and bottom-right (x1, y1) vertices.
        x0 = self.qr.box_size * self.qr.border
        y0 = 0

        x1 = self.qr.box_size * bar_width + x0
        y1 = self.qr.box_size * bar_height + y0

        # We've got everything we need now to generate the progress bar image.
        size = (self.qr.box_size * im_width, self.qr.box_size * im_height)
        progressbar = PIL.Image.new(mode="RGB", size=size, color="white")

        if (bar_width > 0):
            drawer = PIL.ImageDraw.Draw(progressbar)
            drawer.rectangle([x0, y0, x1, y1], fill="black")

        return progressbar

    def _get_qrcode_image(self, data: bytes) -> PIL.Image:
        """Create the QR code component of a QRRR frame.

        Parameters:
            data    Data to be written to the QR code.

        Returns:
            Returns a PIL.Image object with the progress bar drawn.
            There is padding on all edges of the QR code.
        """
        assert len(data) <= self.chunk_size

        self.qr.clear()
        self.qr.add_data(data)
        return self.qr.make_image()

    def build_single_frame(self, data: bytes, progress: float) -> PIL.Image:
        """Create a single frame of a QRRR code containing the provided
        data.

        Parameters:
            data        Data to be written to the QR code.
            progress    Progress of the generated frame (1.0 for 100%)

        Returns:
            Returns a PIL.Image object that is a complete frame of a
            QRRR code. There is padding on all edges of the frame.
        """
        code = self._get_qrcode_image(data)
        pbar = self._get_progressbar_image(progress)

        framesize = (code.size[0], code.size[1] + pbar.size[1])
        frame = PIL.Image.new(mode="RGB", size=framesize, color="white")
        frame.paste(code, (0, 0))
        frame.paste(pbar, (0, code.size[1]))
        return frame

    def build_all_frames(self, data: bytes) -> list[PIL.Image]:
        """Create an entire QRRR code given the provided data.

        Parameters:
            data        Data to be written to the QRRR code.

        Returns:
            Returns an in-order list of PIL.Image objects, each of which
            is a single frame in the animated QRRR object.
        """
        num_chunks = (len(data) + self.chunk_size - 1) // self.chunk_size
        frames = []

        for i in range(num_chunks):
            chunk = data[self.chunk_size * i:self.chunk_size * (i + 1)]
            progress = float(i / (num_chunks - 1))
            frames.append(self.build_single_frame(chunk, progress))

        return frames


class Qrrr(object):
    """Qrrr

    Provides a mechanism to generate a whole QRRR code.
    """
    def __init__(self, version, ecc, fps) -> None:
        """Constructor for Qrrr

        Parameters:
            version     QR code version to be used for the QRRR code.
            ecc         Error correction mode used for the QRRR code.
            fps         Frames per second for the animated QRRR code.
        """
        self.framelength = 1000 // fps
        self.qr = qrcode.QRCode(version=version, error_correction=ecc)
        self.factory = QrrrFrameFactory(self.qr)

    def build(self, source: str) -> str:
        """Build the QRRR code as an animated GIF.

        Parameters:
            source  Source file whose content to convert to QRRR code.

        Returns:
            Returns a string containing the full path of the generated
            animated GIF.
        """
        outfile = os.path.split(source)[-1]
        outfile = os.path.splitext(outfile)[0]
        outfile = f"{outfile}.qrrr.gif"

        with open(source, "br") as f:
            qrrr = self.factory.build_all_frames(f.read())
            qrrr[0].save(
                outfile,
                save_all=True,
                append_images=qrrr[1:],
                optimize=False,
                duration=self.framelength,
                loop=0
            )

        return os.path.abspath(outfile)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ecc", type=str, choices=ECC_MODES, default=ECC_MODES[0],
        help="QR code error correction level"
    )
    parser.add_argument(
        "--fps", type=int, choices=range(1, MAX_FPS + 1), default=5,
        metavar=f"{{1..{MAX_FPS}}}",
        help="FPS for the generated QRRR code (GIF)"
    )
    parser.add_argument(
        "--version", type=int, choices=range(1, MAX_VERSION + 1), default=3,
        metavar=f"{{1..{MAX_VERSION}}}",
        help="QR code version to use."
    )
    parser.add_argument("source", help="File to convert to QRRR code")
    args = parser.parse_args()

    # Argument validation.
    if not os.path.isfile(args.source):
        raise FileNotFoundError(f"Could not find source file '{args.source}'.")

    # Generate the QRRR code.
    qrrr = Qrrr(args.version, ECC_MAP[args.ecc], args.fps)
    generated_file = qrrr.build(args.source)
    print(f"Generated QRRR code:\t{generated_file}")


if __name__ == "__main__":
    main()
