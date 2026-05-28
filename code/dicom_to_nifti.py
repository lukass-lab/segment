#!/usr/bin/env python3
"""Convert a DICOM CT series to NIfTI."""
import sys
import SimpleITK as sitk


def convert(series_dir: str, out_path: str) -> None:
    reader = sitk.ImageSeriesReader()
    file_names = reader.GetGDCMSeriesFileNames(series_dir)
    if not file_names:
        raise RuntimeError(f"No DICOM series found in {series_dir}")
    reader.SetFileNames(file_names)
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()
    image = reader.Execute()
    print(f"size={image.GetSize()} spacing={image.GetSpacing()} origin={image.GetOrigin()}")
    print(f"direction={image.GetDirection()}")
    sitk.WriteImage(image, out_path, useCompression=True)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
