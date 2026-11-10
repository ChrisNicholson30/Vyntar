# Native colour fixture

`srgb-nscolor.bplist` was created on the local macOS host on 2026-11-10 using:

```swift
NSKeyedArchiver.archivedData(
    withRootObject: NSColor(srgbRed: 35.0/255, green: 243.0/255, blue: 244.0/255, alpha: 1),
    requiringSecureCoding: false)
```

The generator retains the keyed archive, sRGB ICC profile (`NSID = 7`) and class metadata. It replaces `NSComponents` and removes the stale `NSRGB` calibrated fallback. No runtime native encoder is needed. AppKit successfully decoded all resulting fields into their intended opaque sRGB channels. Run `tests/verify-native-colors.swift` on macOS to repeat that independent check.

Local Xcode workspace-theme files were read to establish recipe structure and override wrappers; no personal theme is distributed here. Native Xcode round trips remain an acceptance gate. Do not rename a legacy plist into the modern JSON format.
