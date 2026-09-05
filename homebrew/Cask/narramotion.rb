cask "narramotion" do
  version "0.1.0"

  on_arm do
    sha256 "b00ebb293888bc15840f3b1f780c920ef7423c8e4e55bfbb183663a160715864"

    url "https://github.com/byunguk/narramotion/releases/download/v#{version}/narramotion-#{version}-macos-arm64.tar.gz"
  end

  on_intel do
    sha256 "X64_SHA256_HERE"

    url "https://github.com/byunguk/narramotion/releases/download/v#{version}/narramotion-#{version}-macos-x64.tar.gz"
  end

  name "Narramotion"
  desc "Turn narration audio, images, and music into subtitled videos"
  homepage "https://github.com/byunguk/narramotion"

  depends_on arch: :arm64
  depends_on formula: "ffmpeg-full"

  binary "narramotion/narramotion"

  zap trash: [
    "~/.cache/narramotion",
  ]
end