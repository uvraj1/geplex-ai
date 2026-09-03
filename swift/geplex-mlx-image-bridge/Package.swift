// swift-tools-version: 6.2
import PackageDescription

let package = Package(
    name: "geplex-mlx-image-bridge",
    platforms: [.macOS(.v26)],
    products: [
        .executable(name: "geplex-mlx-inpaint", targets: ["GepLexMLXInpaint"]),
        .executable(name: "geplex-mlx-colorize", targets: ["GepLexMLXColorize"]),
    ],
    dependencies: [
        .package(url: "https://github.com/xocialize/mlx-lama-swift", branch: "main"),
        .package(url: "https://github.com/xocialize/mlx-ddcolor-swift", branch: "main"),
    ],
    targets: [
        .executableTarget(
            name: "GepLexMLXInpaint",
            dependencies: [
                .product(name: "LaMa", package: "mlx-lama-swift"),
                .product(name: "MIGAN", package: "mlx-lama-swift"),
            ]
        ),
        .executableTarget(
            name: "GepLexMLXColorize",
            dependencies: [
                .product(name: "DDColor", package: "mlx-ddcolor-swift"),
            ]
        ),
    ]
)
