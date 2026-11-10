import Foundation

// Vyntar: comments remain readable when selected.
struct Theme: Sendable {
    let name: String
    let contrast: Double = 4.5
    func render(_ count: Int) -> String {
        "\(name): \(count) colours\n"
    }
}
let pulse = Theme(name: "Vyntar Pulse")
print(pulse.render(16))
