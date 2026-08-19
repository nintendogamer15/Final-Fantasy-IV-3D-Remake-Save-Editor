#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_label="${1:-v0.6.3}"
output_dir="${2:-${repo_dir}/artifacts}"
dotnet_cmd="${DOTNET_COMMAND:-dotnet}"
safe_label="${release_label//[^A-Za-z0-9._-]/-}"
stage_dir="$(mktemp -d /tmp/ffiv3d-release.XXXXXXXX)"
trap 'rm -rf "${stage_dir}"' EXIT

mkdir -p "${output_dir}"
cd "${repo_dir}"

"${dotnet_cmd}" publish src/FFIV3D.SaveEditor.Gui/FFIV3D.SaveEditor.Gui.csproj \
  --configuration Release --runtime win-x64 --self-contained true \
  -p:PublishSingleFile=true -p:PublishTrimmed=false -p:DebugType=None -p:DebugSymbols=false \
  --output "${stage_dir}/windows"
"${dotnet_cmd}" publish src/FFIV3D.SaveEditor.Gui/FFIV3D.SaveEditor.Gui.csproj \
  --configuration Release --runtime linux-x64 --self-contained true \
  -p:PublishSingleFile=true -p:PublishTrimmed=false -p:DebugType=None -p:DebugSymbols=false \
  --output "${stage_dir}/linux"

windows_asset="${output_dir}/FFIV3DSaveEditor-${safe_label}-windows-x64.exe"
linux_asset="${output_dir}/FFIV3DSaveEditor-${safe_label}-linux-x64"

install -m 0644 "${stage_dir}/windows/FFIV3DSaveEditor.exe" "${windows_asset}"
install -m 0755 "${stage_dir}/linux/FFIV3DSaveEditor" "${linux_asset}"

printf '%s\n' "${windows_asset}" "${linux_asset}"
