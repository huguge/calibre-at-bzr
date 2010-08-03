// Generated by generate.py

static void magick_add_module_constants(PyObject *m) {
    PyModule_AddIntConstant(m, "UndefinedFilter", 0);
    PyModule_AddIntConstant(m, "PointFilter", 1);
    PyModule_AddIntConstant(m, "BoxFilter", 2);
    PyModule_AddIntConstant(m, "TriangleFilter", 3);
    PyModule_AddIntConstant(m, "HermiteFilter", 4);
    PyModule_AddIntConstant(m, "HanningFilter", 5);
    PyModule_AddIntConstant(m, "HammingFilter", 6);
    PyModule_AddIntConstant(m, "BlackmanFilter", 7);
    PyModule_AddIntConstant(m, "GaussianFilter", 8);
    PyModule_AddIntConstant(m, "QuadraticFilter", 9);
    PyModule_AddIntConstant(m, "CubicFilter", 10);
    PyModule_AddIntConstant(m, "CatromFilter", 11);
    PyModule_AddIntConstant(m, "MitchellFilter", 12);
    PyModule_AddIntConstant(m, "LanczosFilter", 13);
    PyModule_AddIntConstant(m, "BesselFilter", 14);
    PyModule_AddIntConstant(m, "SincFilter", 15);
    PyModule_AddIntConstant(m, "KaiserFilter", 16);
    PyModule_AddIntConstant(m, "WelshFilter", 17);
    PyModule_AddIntConstant(m, "ParzenFilter", 18);
    PyModule_AddIntConstant(m, "LagrangeFilter", 19);
    PyModule_AddIntConstant(m, "BohmanFilter", 20);
    PyModule_AddIntConstant(m, "BartlettFilter", 21);
    PyModule_AddIntConstant(m, "SentinelFilter", 22);
    PyModule_AddIntConstant(m, "UndefinedInterpolatePixel", 0);
    PyModule_AddIntConstant(m, "AverageInterpolatePixel", 1);
    PyModule_AddIntConstant(m, "BicubicInterpolatePixel", 2);
    PyModule_AddIntConstant(m, "BilinearInterpolatePixel", 3);
    PyModule_AddIntConstant(m, "FilterInterpolatePixel", 4);
    PyModule_AddIntConstant(m, "IntegerInterpolatePixel", 5);
    PyModule_AddIntConstant(m, "MeshInterpolatePixel", 6);
    PyModule_AddIntConstant(m, "NearestNeighborInterpolatePixel", 7);
    PyModule_AddIntConstant(m, "SplineInterpolatePixel", 8);
    PyModule_AddIntConstant(m, "UndefinedAlphaChannel", 0);
    PyModule_AddIntConstant(m, "ActivateAlphaChannel", 1);
    PyModule_AddIntConstant(m, "BackgroundAlphaChannel", 2);
    PyModule_AddIntConstant(m, "CopyAlphaChannel", 3);
    PyModule_AddIntConstant(m, "DeactivateAlphaChannel", 4);
    PyModule_AddIntConstant(m, "ExtractAlphaChannel", 5);
    PyModule_AddIntConstant(m, "OpaqueAlphaChannel", 6);
    PyModule_AddIntConstant(m, "ResetAlphaChannel", 7);
    PyModule_AddIntConstant(m, "SetAlphaChannel", 8);
    PyModule_AddIntConstant(m, "ShapeAlphaChannel", 9);
    PyModule_AddIntConstant(m, "TransparentAlphaChannel", 10);
    PyModule_AddIntConstant(m, "UndefinedType", 0);
    PyModule_AddIntConstant(m, "BilevelType", 1);
    PyModule_AddIntConstant(m, "GrayscaleType", 2);
    PyModule_AddIntConstant(m, "GrayscaleMatteType", 3);
    PyModule_AddIntConstant(m, "PaletteType", 4);
    PyModule_AddIntConstant(m, "PaletteMatteType", 5);
    PyModule_AddIntConstant(m, "TrueColorType", 6);
    PyModule_AddIntConstant(m, "TrueColorMatteType", 7);
    PyModule_AddIntConstant(m, "ColorSeparationType", 8);
    PyModule_AddIntConstant(m, "ColorSeparationMatteType", 9);
    PyModule_AddIntConstant(m, "OptimizeType", 10);
    PyModule_AddIntConstant(m, "PaletteBilevelMatteType", 11);
    PyModule_AddIntConstant(m, "UndefinedInterlace", 0);
    PyModule_AddIntConstant(m, "NoInterlace", 1);
    PyModule_AddIntConstant(m, "LineInterlace", 2);
    PyModule_AddIntConstant(m, "PlaneInterlace", 3);
    PyModule_AddIntConstant(m, "PartitionInterlace", 4);
    PyModule_AddIntConstant(m, "GIFInterlace", 5);
    PyModule_AddIntConstant(m, "JPEGInterlace", 6);
    PyModule_AddIntConstant(m, "PNGInterlace", 7);
    PyModule_AddIntConstant(m, "UndefinedOrientation", 0);
    PyModule_AddIntConstant(m, "TopLeftOrientation", 1);
    PyModule_AddIntConstant(m, "TopRightOrientation", 2);
    PyModule_AddIntConstant(m, "BottomRightOrientation", 3);
    PyModule_AddIntConstant(m, "BottomLeftOrientation", 4);
    PyModule_AddIntConstant(m, "LeftTopOrientation", 5);
    PyModule_AddIntConstant(m, "RightTopOrientation", 6);
    PyModule_AddIntConstant(m, "RightBottomOrientation", 7);
    PyModule_AddIntConstant(m, "LeftBottomOrientation", 8);
    PyModule_AddIntConstant(m, "UndefinedResolution", 0);
    PyModule_AddIntConstant(m, "PixelsPerInchResolution", 1);
    PyModule_AddIntConstant(m, "PixelsPerCentimeterResolution", 2);
    PyModule_AddIntConstant(m, "UndefinedTransmitType", 0);
    PyModule_AddIntConstant(m, "FileTransmitType", 1);
    PyModule_AddIntConstant(m, "BlobTransmitType", 2);
    PyModule_AddIntConstant(m, "StreamTransmitType", 3);
    PyModule_AddIntConstant(m, "ImageTransmitType", 4);
    PyModule_AddIntConstant(m, "UndefinedAlign", 0);
    PyModule_AddIntConstant(m, "LeftAlign", 1);
    PyModule_AddIntConstant(m, "CenterAlign", 2);
    PyModule_AddIntConstant(m, "RightAlign", 3);
    PyModule_AddIntConstant(m, "UndefinedPathUnits", 0);
    PyModule_AddIntConstant(m, "UserSpace", 1);
    PyModule_AddIntConstant(m, "UserSpaceOnUse", 2);
    PyModule_AddIntConstant(m, "ObjectBoundingBox", 3);
    PyModule_AddIntConstant(m, "UndefinedDecoration", 0);
    PyModule_AddIntConstant(m, "NoDecoration", 1);
    PyModule_AddIntConstant(m, "UnderlineDecoration", 2);
    PyModule_AddIntConstant(m, "OverlineDecoration", 3);
    PyModule_AddIntConstant(m, "LineThroughDecoration", 4);
    PyModule_AddIntConstant(m, "UndefinedDirection", 0);
    PyModule_AddIntConstant(m, "RightToLeftDirection", 1);
    PyModule_AddIntConstant(m, "LeftToRightDirection", 2);
    PyModule_AddIntConstant(m, "UndefinedRule", 0);
    PyModule_AddIntConstant(m, "EvenOddRule", 1);
    PyModule_AddIntConstant(m, "NonZeroRule", 2);
    PyModule_AddIntConstant(m, "UndefinedGradient", 0);
    PyModule_AddIntConstant(m, "LinearGradient", 1);
    PyModule_AddIntConstant(m, "RadialGradient", 2);
    PyModule_AddIntConstant(m, "UndefinedCap", 0);
    PyModule_AddIntConstant(m, "ButtCap", 1);
    PyModule_AddIntConstant(m, "RoundCap", 2);
    PyModule_AddIntConstant(m, "SquareCap", 3);
    PyModule_AddIntConstant(m, "UndefinedJoin", 0);
    PyModule_AddIntConstant(m, "MiterJoin", 1);
    PyModule_AddIntConstant(m, "RoundJoin", 2);
    PyModule_AddIntConstant(m, "BevelJoin", 3);
    PyModule_AddIntConstant(m, "UndefinedMethod", 0);
    PyModule_AddIntConstant(m, "PointMethod", 1);
    PyModule_AddIntConstant(m, "ReplaceMethod", 2);
    PyModule_AddIntConstant(m, "FloodfillMethod", 3);
    PyModule_AddIntConstant(m, "FillToBorderMethod", 4);
    PyModule_AddIntConstant(m, "ResetMethod", 5);
    PyModule_AddIntConstant(m, "UndefinedPrimitive", 0);
    PyModule_AddIntConstant(m, "PointPrimitive", 1);
    PyModule_AddIntConstant(m, "LinePrimitive", 2);
    PyModule_AddIntConstant(m, "RectanglePrimitive", 3);
    PyModule_AddIntConstant(m, "RoundRectanglePrimitive", 4);
    PyModule_AddIntConstant(m, "ArcPrimitive", 5);
    PyModule_AddIntConstant(m, "EllipsePrimitive", 6);
    PyModule_AddIntConstant(m, "CirclePrimitive", 7);
    PyModule_AddIntConstant(m, "PolylinePrimitive", 8);
    PyModule_AddIntConstant(m, "PolygonPrimitive", 9);
    PyModule_AddIntConstant(m, "BezierPrimitive", 10);
    PyModule_AddIntConstant(m, "ColorPrimitive", 11);
    PyModule_AddIntConstant(m, "MattePrimitive", 12);
    PyModule_AddIntConstant(m, "TextPrimitive", 13);
    PyModule_AddIntConstant(m, "ImagePrimitive", 14);
    PyModule_AddIntConstant(m, "PathPrimitive", 15);
    PyModule_AddIntConstant(m, "UndefinedReference", 0);
    PyModule_AddIntConstant(m, "GradientReference", 1);
    PyModule_AddIntConstant(m, "UndefinedSpread", 0);
    PyModule_AddIntConstant(m, "PadSpread", 1);
    PyModule_AddIntConstant(m, "ReflectSpread", 2);
    PyModule_AddIntConstant(m, "RepeatSpread", 3);
    PyModule_AddIntConstant(m, "UndefinedDistortion", 0);
    PyModule_AddIntConstant(m, "AffineDistortion", 1);
    PyModule_AddIntConstant(m, "AffineProjectionDistortion", 2);
    PyModule_AddIntConstant(m, "ScaleRotateTranslateDistortion", 3);
    PyModule_AddIntConstant(m, "PerspectiveDistortion", 4);
    PyModule_AddIntConstant(m, "PerspectiveProjectionDistortion", 5);
    PyModule_AddIntConstant(m, "BilinearForwardDistortion", 6);
    PyModule_AddIntConstant(m, "BilinearDistortion", 6);
    PyModule_AddIntConstant(m, "BilinearReverseDistortion", 7);
    PyModule_AddIntConstant(m, "PolynomialDistortion", 8);
    PyModule_AddIntConstant(m, "ArcDistortion", 9);
    PyModule_AddIntConstant(m, "PolarDistortion", 10);
    PyModule_AddIntConstant(m, "DePolarDistortion", 11);
    PyModule_AddIntConstant(m, "BarrelDistortion", 12);
    PyModule_AddIntConstant(m, "BarrelInverseDistortion", 13);
    PyModule_AddIntConstant(m, "ShepardsDistortion", 14);
    PyModule_AddIntConstant(m, "SentinelDistortion", 15);
    PyModule_AddIntConstant(m, "UndefinedColorInterpolate", 0);
    PyModule_AddIntConstant(m, "BarycentricColorInterpolate", 1);
    PyModule_AddIntConstant(m, "BilinearColorInterpolate", 7);
    PyModule_AddIntConstant(m, "PolynomialColorInterpolate", 8);
    PyModule_AddIntConstant(m, "ShepardsColorInterpolate", 14);
    PyModule_AddIntConstant(m, "VoronoiColorInterpolate", 15);
    PyModule_AddIntConstant(m, "UndefinedCompositeOp", 0);
    PyModule_AddIntConstant(m, "NoCompositeOp", 1);
    PyModule_AddIntConstant(m, "ModulusAddCompositeOp", 2);
    PyModule_AddIntConstant(m, "AtopCompositeOp", 3);
    PyModule_AddIntConstant(m, "BlendCompositeOp", 4);
    PyModule_AddIntConstant(m, "BumpmapCompositeOp", 5);
    PyModule_AddIntConstant(m, "ChangeMaskCompositeOp", 6);
    PyModule_AddIntConstant(m, "ClearCompositeOp", 7);
    PyModule_AddIntConstant(m, "ColorBurnCompositeOp", 8);
    PyModule_AddIntConstant(m, "ColorDodgeCompositeOp", 9);
    PyModule_AddIntConstant(m, "ColorizeCompositeOp", 10);
    PyModule_AddIntConstant(m, "CopyBlackCompositeOp", 11);
    PyModule_AddIntConstant(m, "CopyBlueCompositeOp", 12);
    PyModule_AddIntConstant(m, "CopyCompositeOp", 13);
    PyModule_AddIntConstant(m, "CopyCyanCompositeOp", 14);
    PyModule_AddIntConstant(m, "CopyGreenCompositeOp", 15);
    PyModule_AddIntConstant(m, "CopyMagentaCompositeOp", 16);
    PyModule_AddIntConstant(m, "CopyOpacityCompositeOp", 17);
    PyModule_AddIntConstant(m, "CopyRedCompositeOp", 18);
    PyModule_AddIntConstant(m, "CopyYellowCompositeOp", 19);
    PyModule_AddIntConstant(m, "DarkenCompositeOp", 20);
    PyModule_AddIntConstant(m, "DstAtopCompositeOp", 21);
    PyModule_AddIntConstant(m, "DstCompositeOp", 22);
    PyModule_AddIntConstant(m, "DstInCompositeOp", 23);
    PyModule_AddIntConstant(m, "DstOutCompositeOp", 24);
    PyModule_AddIntConstant(m, "DstOverCompositeOp", 25);
    PyModule_AddIntConstant(m, "DifferenceCompositeOp", 26);
    PyModule_AddIntConstant(m, "DisplaceCompositeOp", 27);
    PyModule_AddIntConstant(m, "DissolveCompositeOp", 28);
    PyModule_AddIntConstant(m, "ExclusionCompositeOp", 29);
    PyModule_AddIntConstant(m, "HardLightCompositeOp", 30);
    PyModule_AddIntConstant(m, "HueCompositeOp", 31);
    PyModule_AddIntConstant(m, "InCompositeOp", 32);
    PyModule_AddIntConstant(m, "LightenCompositeOp", 33);
    PyModule_AddIntConstant(m, "LinearLightCompositeOp", 34);
    PyModule_AddIntConstant(m, "LuminizeCompositeOp", 35);
    PyModule_AddIntConstant(m, "MinusCompositeOp", 36);
    PyModule_AddIntConstant(m, "ModulateCompositeOp", 37);
    PyModule_AddIntConstant(m, "MultiplyCompositeOp", 38);
    PyModule_AddIntConstant(m, "OutCompositeOp", 39);
    PyModule_AddIntConstant(m, "OverCompositeOp", 40);
    PyModule_AddIntConstant(m, "OverlayCompositeOp", 41);
    PyModule_AddIntConstant(m, "PlusCompositeOp", 42);
    PyModule_AddIntConstant(m, "ReplaceCompositeOp", 43);
    PyModule_AddIntConstant(m, "SaturateCompositeOp", 44);
    PyModule_AddIntConstant(m, "ScreenCompositeOp", 45);
    PyModule_AddIntConstant(m, "SoftLightCompositeOp", 46);
    PyModule_AddIntConstant(m, "SrcAtopCompositeOp", 47);
    PyModule_AddIntConstant(m, "SrcCompositeOp", 48);
    PyModule_AddIntConstant(m, "SrcInCompositeOp", 49);
    PyModule_AddIntConstant(m, "SrcOutCompositeOp", 50);
    PyModule_AddIntConstant(m, "SrcOverCompositeOp", 51);
    PyModule_AddIntConstant(m, "ModulusSubtractCompositeOp", 52);
    PyModule_AddIntConstant(m, "ThresholdCompositeOp", 53);
    PyModule_AddIntConstant(m, "XorCompositeOp", 54);
    PyModule_AddIntConstant(m, "DivideCompositeOp", 55);
    PyModule_AddIntConstant(m, "DistortCompositeOp", 56);
    PyModule_AddIntConstant(m, "BlurCompositeOp", 57);
    PyModule_AddIntConstant(m, "PegtopLightCompositeOp", 58);
    PyModule_AddIntConstant(m, "VividLightCompositeOp", 59);
    PyModule_AddIntConstant(m, "PinLightCompositeOp", 60);
    PyModule_AddIntConstant(m, "LinearDodgeCompositeOp", 61);
    PyModule_AddIntConstant(m, "LinearBurnCompositeOp", 62);
    PyModule_AddIntConstant(m, "MathematicsCompositeOp", 63);
}
