import CoreGraphics
import Foundation
import ImageIO
import Vision

guard CommandLine.arguments.count == 2 else {
    FileHandle.standardError.write(Data("usage: analyze_reference_image.swift IMAGE\n".utf8))
    exit(2)
}

let imageURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard
    let source = CGImageSourceCreateWithURL(imageURL as CFURL, nil),
    let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
else {
    FileHandle.standardError.write(Data("could not decode image\n".utf8))
    exit(3)
}

func horizontalPosition(_ box: CGRect) -> String {
    let center = box.midX
    if center < 0.34 { return "left" }
    if center > 0.66 { return "right" }
    return "center"
}

func verticalPosition(_ box: CGRect) -> String {
    let center = box.midY
    if center < 0.34 { return "lower" }
    if center > 0.66 { return "upper" }
    return "middle"
}

func boxRecord(_ box: CGRect) -> [String: Any] {
    return [
        "horizontal": horizontalPosition(box),
        "vertical": verticalPosition(box),
        "x": Double(box.origin.x),
        "y": Double(box.origin.y),
        "width": Double(box.width),
        "height": Double(box.height),
    ]
}

let classification = VNClassifyImageRequest()
let textRequest = VNRecognizeTextRequest()
textRequest.recognitionLevel = .accurate
textRequest.usesLanguageCorrection = true
let faceRequest = VNDetectFaceRectanglesRequest()
let humanRequest = VNDetectHumanRectanglesRequest()

// Some Vision requests may be unavailable on a particular Mac. Run them
// independently so OCR or layout detection can still produce a useful brief.
var analysisWarnings: [String] = []
let requests: [(String, VNRequest)] = [
    ("visual classification", classification),
    ("text recognition", textRequest),
    ("face placement", faceRequest),
    ("figure placement", humanRequest),
]
for (name, request) in requests {
    do {
        try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    } catch {
        analysisWarnings.append("\(name) was unavailable")
        continue
    }
}

let labels: [[String: Any]] = (classification.results ?? [])
    .filter { $0.confidence >= 0.045 }
    .prefix(12)
    .map { ["label": $0.identifier, "confidence": Double($0.confidence)] }

let recognizedText: [[String: Any]] = (textRequest.results ?? []).compactMap { observation in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    var record = boxRecord(observation.boundingBox)
    record["text"] = candidate.string
    record["confidence"] = Double(candidate.confidence)
    return record
}

let faces = (faceRequest.results ?? []).map { boxRecord($0.boundingBox) }
let humans = (humanRequest.results ?? []).map { boxRecord($0.boundingBox) }

var dominantHex: String? = nil
let sampleWidth = 64
let sampleHeight = 64
var pixels = [UInt8](repeating: 0, count: sampleWidth * sampleHeight * 4)
let rendered = pixels.withUnsafeMutableBytes { rawBuffer -> Bool in
    guard let context = CGContext(
        data: rawBuffer.baseAddress,
        width: sampleWidth,
        height: sampleHeight,
        bitsPerComponent: 8,
        bytesPerRow: sampleWidth * 4,
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else { return false }
    context.interpolationQuality = .medium
    context.draw(image, in: CGRect(x: 0, y: 0, width: sampleWidth, height: sampleHeight))
    return true
}
if rendered {
    var red = 0
    var green = 0
    var blue = 0
    var count = 0
    for offset in stride(from: 0, to: pixels.count, by: 4) where pixels[offset + 3] > 16 {
        red += Int(pixels[offset])
        green += Int(pixels[offset + 1])
        blue += Int(pixels[offset + 2])
        count += 1
    }
    if count > 0 {
        dominantHex = String(format: "#%02X%02X%02X", red / count, green / count, blue / count)
    }
}

let width = image.width
let height = image.height
let orientation: String
if abs(Double(width - height)) / Double(max(width, height)) < 0.08 {
    orientation = "square"
} else if width > height {
    orientation = "landscape"
} else {
    orientation = "portrait"
}

var output: [String: Any] = [
    "width": width,
    "height": height,
    "orientation": orientation,
    "classification_labels": labels,
    "recognized_text": recognizedText,
    "faces": faces,
    "human_figures": humans,
    "analysis_warnings": analysisWarnings,
]
if let dominantHex = dominantHex { output["average_color"] = dominantHex }

let encoded = try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys])
FileHandle.standardOutput.write(encoded)
FileHandle.standardOutput.write(Data("\n".utf8))
