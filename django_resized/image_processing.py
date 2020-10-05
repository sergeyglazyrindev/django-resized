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
        self.img.thumbnail(
            size,
            method
        )
        return self.img

    def save_to_the_buffer(self, compression_format, quality, **img_info):
        new_content = BytesIO()
        self.img.save(new_content, format=compression_format, quality=quality, **img_info)
        new_content = ContentFile(new_content.getvalue())
        return new_content


def thumbnails(img, size, centering=None, method=Image.ANTIALIAS):
    last_frame = img.convert('RGBA')
    p = img.getpalette()
    mode = analyseImage(img)['mode']
    all_frames = []
    frames = ImageSequence.Iterator(img)
    for frame in frames:
        if not frame.getpalette():
            frame.putpalette(p)
        new_frame = Image.new('RGBA', img.size)
        if mode == 'partial':
            new_frame.paste(last_frame)
        new_frame.paste(frame, (0, 0), frame.convert('RGBA'))
        last_frame = new_frame.copy()
        if centering:
            new_frame = ImageOps.fit(
                new_frame,
                size,
                method,
                centering=centering
            )
        else:
            new_frame.thumbnail(size, Image.ANTIALIAS)
        all_frames.append(new_frame)
    return all_frames


def cropped_thumbnails(img, box, method=Image.ANTIALIAS):
    last_frame = img.convert('RGBA')
    p = img.getpalette()
    mode = analyseImage(img)['mode']
    all_frames = []
    frames = ImageSequence.Iterator(img)
    for frame in frames:
        if not frame.getpalette():
            frame.putpalette(p)
        new_frame = Image.new('RGBA', img.size)
        if mode == 'partial':
            new_frame.paste(last_frame)
        new_frame.paste(frame, (0, 0), frame.convert('RGBA'))
        last_frame = new_frame.copy()
        new_frame = new_frame.crop(box)
        all_frames.append(new_frame)
    return all_frames


def clone_gif_thumbnails(img):
    last_frame = img.convert('RGBA')
    p = img.getpalette()
    mode = analyseImage(img)['mode']
    all_frames = []
    frames = ImageSequence.Iterator(img)
    for frame in frames:
        if not frame.getpalette():
            frame.putpalette(p)
        new_frame = Image.new('RGBA', img.size)
        if mode == 'partial':
            new_frame.paste(last_frame)
        new_frame.paste(frame, (0, 0), frame.convert('RGBA'))
        last_frame = new_frame.copy()
        all_frames.append(new_frame)
    return all_frames


def analyseImage(im):
    """
    Pre-process pass over the image to determine the mode (full or additive).
    Necessary as assessing single frames isn't reliable. Need to know the mode
    before processing all frames.
    """
    results = {
        'size': im.size,
        'mode': 'full',
    }
    try:
        while True:
            if im.tile:
                tile = im.tile[0]
                update_region = tile[1]
                update_region_dimensions = update_region[2:]
                if update_region_dimensions != im.size:
                    results['mode'] = 'partial'
                    break
            im.seek(im.tell() + 1)
    except EOFError:
        pass
    return results


class AnimatedGifImageProcessingFactory(IImageProcessingFactory):

    def crop(self, size, centering, method=Image.ANTIALIAS):
        frames = thumbnails(self.img, size, centering=centering, method=method)
        om = frames[0]
        new_content = BytesIO()
        om.save(new_content, optimize=True, format='gif', save_all=True, append_images=frames[1:], duration=self.img.info.get('duration'), loop=self.img.info.get('loop'))
        self.img = Image.open(new_content)
        return self.img

    def arbitrary_cropping(self, size, box, method=Image.ANTIALIAS):
        frames = cropped_thumbnails(self.img, box, method=method)
        om = frames[0]
        new_content = BytesIO()
        om.save(new_content, optimize=True, format='gif', save_all=True, append_images=frames[1:], duration=self.img.info.get('duration'), loop=self.img.info.get('loop')) # , save_all=True, append_images=frames
        self.img = Image.open(new_content)
        return self.img

    def make_thumbnail(self, size, method=Image.ANTIALIAS):
        frames = thumbnails(self.img, size, method=method)
        om = frames[0]
        new_content = BytesIO()
        om.save(new_content, optimize=True, format='gif', save_all=True, append_images=frames[1:], duration=self.img.info.get('duration'), loop=self.img.info.get('loop'))
        self.img = Image.open(new_content)
        return self.img

    def save_to_the_buffer(self, compression_format, quality, **img_info):
        new_content = BytesIO()
        frames = clone_gif_thumbnails(self.img)
        om = frames[0]
        om.info = self.img.info
        om.save(new_content, format='gif', optimize=True, save_all=True, append_images=frames[1:], duration=self.img.info.get('duration'), loop=self.img.info.get('loop'))
        new_content = ContentFile(new_content.getvalue())
        return new_content


def make_factory_for_image_processing(img):
    factory_per_img_format = {
        'default': DefaultImageProcessingFactory,
    }
    if img.format.lower() == 'gif':
        frames = ImageSequence.Iterator(img)
        if len(list(frames)) > 1:
            return AnimatedGifImageProcessingFactory(img)
    return factory_per_img_format['default'](img)
