from abc import ABCMeta, abstractmethod
from io import BytesIO

from django.core.files.base import ContentFile

from PIL import Image, ImageOps, ImageSequence


class IImageProcessingFactory(metaclass=ABCMeta):

    def __init__(self, img):
        self.img = img

    @abstractmethod
    def crop(self, size, centering, method=Image.ANTIALIAS):
        raise NotImplementedError

    @abstractmethod
    def make_thumbnail(self, size, method=Image.ANTIALIAS):
        raise NotImplementedError

    @abstractmethod
    def save_to_the_buffer(self, compression_format, quality, **img_info):
        raise NotImplementedError


class DefaultImageProcessingFactory(IImageProcessingFactory):

    def crop(self, size, centering, method=Image.ANTIALIAS):
        self.img = ImageOps.fit(
            self.img,
            size,
            method,
            centering=centering
        )
        return self.img

    def make_thumbnail(self, size, method=Image.ANTIALIAS):
        self.img = self.img.thumbnail(
            size,
            method
        )
        return self.img

    def save_to_the_buffer(self, compression_format, quality, **img_info):
        new_content = BytesIO()
        self.img.save(new_content, format=compression_format, quality=quality, **img_info)
        new_content = ContentFile(new_content.getvalue())
        return new_content


# Wrap on-the-fly thumbnail generator
def thumbnails(frames, size, centering=None, method=Image.ANTIALIAS):
    for frame in frames:
        thumbnail = frame.copy()
        if centering:
            thumbnail = ImageOps.fit(
                thumbnail,
                size,
                method,
                centering=centering
            )
        else:
            thumbnail.thumbnail(size, Image.ANTIALIAS)
        yield thumbnail


def cropped_thumbnails(frames, size, box, method=Image.ANTIALIAS):
    for frame in frames:
        thumbnail = frame.copy()
        thumbnail = thumbnail.crop(
            box
        )
        yield thumbnail


class GifImageProcessingFactory(IImageProcessingFactory):

    def crop(self, size, centering, method=Image.ANTIALIAS):
        frames = ImageSequence.Iterator(self.img)
        frames = thumbnails(frames, size, centering=centering, method=method)
        om = next(frames)
        om.info = self.img.info
        new_content = BytesIO()
        om.save(new_content, format='gif', save_all=True, append_images=list(frames))
        self.img = Image.frombuffer(om.mode, size, new_content)
        return self.img

    def arbitrary_cropping(self, size, box, method=Image.ANTIALIAS):
        frames = ImageSequence.Iterator(self.img)
        frames = cropped_thumbnails(frames, size, box, method=method)
        om = next(frames)
        om.info = self.img.info
        new_content = BytesIO()
        om.save(new_content, format='gif', save_all=True, append_images=list(frames))
        self.img = Image.frombuffer(om.mode, size, new_content)
        return self.img

    def make_thumbnail(self, size, method=Image.ANTIALIAS):
        frames = ImageSequence.Iterator(self.img)
        frames = thumbnails(frames, size, method=method)
        om = next(frames)
        om.info = self.img.info
        new_content = BytesIO()
        om.save(new_content, format='gif', save_all=True, append_images=list(frames))
        self.img = Image.frombuffer(om.mode, size, new_content)
        return self.img

    def save_to_the_buffer(self, compression_format, quality, **img_info):
        new_content = BytesIO()
        frames = ImageSequence.Iterator(self.img)
        om = next(frames)
        om.info = self.img.info
        om.save(new_content, format='gif', save_all=True, append_images=list(frames))
        new_content = ContentFile(new_content.getvalue())
        return new_content


def make_factory_for_image_processing(img):
    factory_per_img_format = {
        'default': DefaultImageProcessingFactory,
        'gif': GifImageProcessingFactory
    }
    if img.format.lower() not in factory_per_img_format:
        return factory_per_img_format['default'](img)
    return factory_per_img_format[img.format.lower()](img)
