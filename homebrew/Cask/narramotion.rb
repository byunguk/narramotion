cask "narramotion" do
  version "0.1.0"
  sha256 "REPLACE_WITH_RELEASE_SHA256"

  on_arm do
    url "https://github.com/YOUR_GITHUB_USER/narramotion/releases/download/v#{version}/narramotion-macos-arm64.tar.gz"
  end

  on_intel do
    url "https://github.com/YOUR_GITHUB_USER/narramotion/releases/download/v#{version}/narramotion-macos-x64.tar.gz"
  end

  name "Narramotion"
  desc "Batch Bible narration trimming, Gemini subtitles, and FFmpeg video rendering"
  homepage "https://github.com/YOUR_GITHUB_USER/narramotion"

  depends_on formula: "ffmpeg-full"

  binary "narramotion"

  zap trash: [
    "~/.cache/narramotion",
  ]
end
