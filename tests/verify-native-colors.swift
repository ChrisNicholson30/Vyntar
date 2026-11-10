// Run: swift tests/verify-native-colors.swift themes/terminal/*.terminal
import AppKit
for path in CommandLine.arguments.dropFirst() {
    let data = try Data(contentsOf: URL(fileURLWithPath: path))
    let profile = try PropertyListSerialization.propertyList(from: data, format: nil) as! [String:Any]
    var count = 0
    for (key, value) in profile where value is Data {
        let archive = value as! Data
        let dict = try PropertyListSerialization.propertyList(from: archive, format: nil) as! [String:Any]
        let objects = dict["$objects"] as! [Any]
        let colourData = objects[1] as! [String:Any]
        let components = String(data: colourData["NSComponents"] as! Data, encoding: .utf8)!.split(separator: " ").map { Double($0)! }
        let colour = try NSKeyedUnarchiver.unarchivedObject(ofClass: NSColor.self, from: archive)!.usingColorSpace(.sRGB)!
        let actual = [colour.redComponent, colour.greenComponent, colour.blueComponent, colour.alphaComponent]
        for (a, b) in zip(actual, components) {
            precondition(abs(a-b) < 1e-8, "sRGB mismatch: \(key)")
        }
        count += 1
    }
    precondition(count == 21, "Expected 21 colour fields")
    print("Verified \(count) native sRGB fields: \(path)")
}
