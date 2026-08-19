%{!?app_version:%global app_version 0.0.0}
%global debug_package %{nil}
%global _build_id_links none
%global __strip /bin/true
%global source_date_epoch_from_changelog 0

Name:           ffiv3d-save-editor
Version:        %{app_version}
Release:        1
Summary:        Final Fantasy IV 3D Remake save editor
License:        LGPL-3.0-or-later
URL:            https://github.com/nintendogamer15/Final-Fantasy-IV-3D-Remake-Save-Editor
Source0:        app-binary
Source1:        ffiv3d-save-editor.desktop
Source2:        io.github.nintendogamer15.FFIV3DSaveEditor.metainfo.xml
Source3:        icon.png
Source4:        LICENSE
Source5:        COPYING
Source6:        COPYING.LESSER
Source7:        ADDITIONAL_PERMISSIONS.md
Source8:        THIRD_PARTY_NOTICES.md
Source9:        README_LICENSE_SUMMARY.txt
Source10:       FFIV-Save-Editor-LGPL-3.0.txt
Source11:       MIT.txt

ExclusiveArch:  x86_64
BuildRequires:  appstream
BuildRequires:  desktop-file-utils
Requires:       ca-certificates
Requires:       fontconfig
Requires:       glibc
Requires:       hicolor-icon-theme
Requires:       krb5-libs
Requires:       libgcc
Requires:       libICE
Requires:       libicu
Requires:       libSM
Requires:       libstdc++
Requires:       libX11
Requires:       openssl-libs
Requires:       tzdata
Requires:       zlib-ng-compat
Recommends:     xdg-desktop-portal

%description
A self-contained Avalonia desktop editor for the PC Final Fantasy IV 3D
Remake SAVE.BIN format, including checksum and redundant-copy handling.

%prep

%build

%install
install -Dm0755 %{SOURCE0} %{buildroot}%{_bindir}/ffiv3d-save-editor
desktop-file-install --dir=%{buildroot}%{_datadir}/applications %{SOURCE1}
install -Dm0644 %{SOURCE2} \
  %{buildroot}%{_datadir}/metainfo/io.github.nintendogamer15.FFIV3DSaveEditor.metainfo.xml
install -Dm0644 %{SOURCE3} \
  %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/ffiv3d-save-editor.png

install -Dm0644 %{SOURCE4} %{buildroot}%{_licensedir}/%{name}/LICENSE
install -Dm0644 %{SOURCE5} %{buildroot}%{_licensedir}/%{name}/COPYING
install -Dm0644 %{SOURCE6} %{buildroot}%{_licensedir}/%{name}/COPYING.LESSER
install -Dm0644 %{SOURCE10} %{buildroot}%{_licensedir}/%{name}/FFIV-Save-Editor-LGPL-3.0.txt
install -Dm0644 %{SOURCE11} %{buildroot}%{_licensedir}/%{name}/MIT.txt
install -Dm0644 %{SOURCE7} %{buildroot}%{_docdir}/%{name}/ADDITIONAL_PERMISSIONS.md
install -Dm0644 %{SOURCE8} %{buildroot}%{_docdir}/%{name}/THIRD_PARTY_NOTICES.md
install -Dm0644 %{SOURCE9} %{buildroot}%{_docdir}/%{name}/README_LICENSE_SUMMARY.txt

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/ffiv3d-save-editor.desktop
appstreamcli validate --no-net \
  %{buildroot}%{_datadir}/metainfo/io.github.nintendogamer15.FFIV3DSaveEditor.metainfo.xml

%files
%{_bindir}/ffiv3d-save-editor
%{_datadir}/applications/ffiv3d-save-editor.desktop
%{_datadir}/icons/hicolor/256x256/apps/ffiv3d-save-editor.png
%{_datadir}/metainfo/io.github.nintendogamer15.FFIV3DSaveEditor.metainfo.xml
%license %{_licensedir}/%{name}/LICENSE
%license %{_licensedir}/%{name}/COPYING
%license %{_licensedir}/%{name}/COPYING.LESSER
%license %{_licensedir}/%{name}/FFIV-Save-Editor-LGPL-3.0.txt
%license %{_licensedir}/%{name}/MIT.txt
%doc %{_docdir}/%{name}/ADDITIONAL_PERMISSIONS.md
%doc %{_docdir}/%{name}/THIRD_PARTY_NOTICES.md
%doc %{_docdir}/%{name}/README_LICENSE_SUMMARY.txt

%changelog
* Tue Aug 18 2026 Robert - 0.6.3-1
- Add native Fedora packaging for the self-contained application.
