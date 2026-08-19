#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <vX.Y.Z|X.Y.Z> <linux-binary> <output-directory>" >&2
  exit 2
fi

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="${1#v}"
binary="$(realpath "$2")"
output_dir="$(realpath -m "$3")"
[[ ${version} =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Invalid package version: ${version}" >&2; exit 2; }
[[ -f ${binary} && -x ${binary} ]] || { echo "Linux binary is missing or not executable: ${binary}" >&2; exit 2; }

top_dir="$(mktemp -d /tmp/ffiv3d-rpm-package.XXXXXXXX)"
trap 'rm -rf "${top_dir}"' EXIT
mkdir -p "${top_dir}"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS} "${output_dir}"

install -m 0755 "${binary}" "${top_dir}/SOURCES/app-binary"
install -m 0644 "${repo_dir}/packaging/linux/ffiv3d-save-editor.desktop" \
  "${top_dir}/SOURCES/ffiv3d-save-editor.desktop"
install -m 0644 "${repo_dir}/packaging/linux/io.github.nintendogamer15.FFIV3DSaveEditor.metainfo.xml" \
  "${top_dir}/SOURCES/io.github.nintendogamer15.FFIV3DSaveEditor.metainfo.xml"
install -m 0644 "${repo_dir}/assets/icon.png" "${top_dir}/SOURCES/icon.png"
for file in LICENSE COPYING COPYING.LESSER ADDITIONAL_PERMISSIONS.md THIRD_PARTY_NOTICES.md README_LICENSE_SUMMARY.txt; do
  install -m 0644 "${repo_dir}/${file}" "${top_dir}/SOURCES/${file}"
done
install -m 0644 "${repo_dir}/licenses/FFIV-Save-Editor-LGPL-3.0.txt" \
  "${top_dir}/SOURCES/FFIV-Save-Editor-LGPL-3.0.txt"
install -m 0644 "${repo_dir}/licenses/MIT.txt" "${top_dir}/SOURCES/MIT.txt"
install -m 0644 "${repo_dir}/packaging/rpm/ffiv3d-save-editor.spec" \
  "${top_dir}/SPECS/ffiv3d-save-editor.spec"

rpmbuild -bb --define "_topdir ${top_dir}" --define "app_version ${version}" \
  "${top_dir}/SPECS/ffiv3d-save-editor.spec"

package="$(find "${top_dir}/RPMS/x86_64" -maxdepth 1 -type f -name 'ffiv3d-save-editor-*.x86_64.rpm' -print -quit)"
[[ -n ${package} ]] || { echo "Expected RPM package was not produced." >&2; exit 1; }
destination="${output_dir}/$(basename "${package}")"
install -m 0644 "${package}" "${destination}"
printf '%s\n' "${destination}"
