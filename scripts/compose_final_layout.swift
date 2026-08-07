import AppKit
import Foundation

struct LayoutError: Error, CustomStringConvertible {
    let description: String
}

func rgb(_ color: NSColor) -> (Int, Int, Int) {
    guard let converted = color.usingColorSpace(.deviceRGB) else { return (0, 0, 0) }
    return (
        Int((converted.redComponent * 255.0).rounded()),
        Int((converted.greenComponent * 255.0).rounded()),
        Int((converted.blueComponent * 255.0).rounded())
    )
}

func parseHex(_ value: String) -> (Int, Int, Int)? {
    let text = value.trimmingCharacters(in: .whitespacesAndNewlines)
    guard text.range(of: #"^#[0-9a-fA-F]{6}$"#, options: .regularExpression) != nil else { return nil }
    let scanner = Scanner(string: String(text.dropFirst()))
    var number: UInt64 = 0
    guard scanner.scanHexInt64(&number) else { return nil }
    return (Int((number >> 16) & 255), Int((number >> 8) & 255), Int(number & 255))
}

do {
    guard CommandLine.arguments.count >= 4 else { throw LayoutError(description: "Expected source, target, and optional background") }
    let sourceURL = URL(fileURLWithPath: CommandLine.arguments[1])
    let targetURL = URL(fileURLWithPath: CommandLine.arguments[2])
    let override = parseHex(CommandLine.arguments[3])
    guard let data = try? Data(contentsOf: sourceURL), let source = NSBitmapImageRep(data: data) else {
        throw LayoutError(description: "The selected image could not be decoded")
    }
    let width = source.pixelsWide
    let height = source.pixelsHigh
    guard width > 0, height > 0, width % 4 == 0 else { throw LayoutError(description: "Source width must support an exact 80/20 layout") }
    let finalWidth = width * 5 / 4

    var counts: [String: (Int, Int, Int, Int)] = [:]
    func countPixel(_ x: Int, _ y: Int) {
        guard let color = source.colorAt(x: x, y: y) else { return }
        let value = rgb(color)
        let key = "\(value.0),\(value.1),\(value.2)"
        let prior = counts[key]?.3 ?? 0
        counts[key] = (value.0, value.1, value.2, prior + 1)
    }
    for x in 0..<width { countPixel(x, 0); countPixel(x, height - 1) }
    if height > 2 { for y in 1..<(height - 1) { countPixel(0, y); countPixel(width - 1, y) } }
    let detected = counts.values.max { $0.3 < $1.3 }
    let total = max(1, width * 2 + max(0, height - 2) * 2)
    guard override != nil || (detected != nil && Double(detected!.3) / Double(total) >= 0.12) else {
        throw LayoutError(description: "No safe perimeter background color was detected")
    }
    let background = override ?? (detected!.0, detected!.1, detected!.2)
    guard background != (255, 255, 255) else { throw LayoutError(description: "White is not a valid automatic extension color") }

    guard let output = NSBitmapImageRep(
        bitmapDataPlanes: nil, pixelsWide: finalWidth, pixelsHigh: height,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0
    ) else { throw LayoutError(description: "Could not allocate final canvas") }
    let fill = NSColor(deviceRed: CGFloat(background.0) / 255.0, green: CGFloat(background.1) / 255.0, blue: CGFloat(background.2) / 255.0, alpha: 1)
    for y in 0..<height {
        for x in 0..<finalWidth {
            if x < width, let color = source.colorAt(x: x, y: y) { output.setColor(color, atX: x, y: y) }
            else { output.setColor(fill, atX: x, y: y) }
        }
    }
    for y in 0..<height {
        for x in width..<finalWidth {
            guard let color = output.colorAt(x: x, y: y), rgb(color) == background else {
                throw LayoutError(description: "Right extension validation failed")
            }
        }
    }
    guard let png = output.representation(using: .png, properties: [:]) else { throw LayoutError(description: "Could not encode final PNG") }
    try png.write(to: targetURL, options: .atomic)
    let payload: [String: Any] = ["width": width, "height": height, "final_width": finalWidth, "background": [background.0, background.1, background.2]]
    let json = try JSONSerialization.data(withJSONObject: payload)
    print(String(data: json, encoding: .utf8)!)
} catch {
    FileHandle.standardError.write(Data("\(error)\n".utf8))
    exit(1)
}
