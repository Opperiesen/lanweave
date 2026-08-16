# Lanweave v1.0.1

Lanweave v1.0.1 is a patch release for the stable v1.0 local network
control-plane. It refreshes the public presentation of the package without
changing runtime behavior, public contracts or controller compatibility.

## Included

- minimal Lanweave visual identity and woven-W logo;
- release-stable absolute logo URL in the README for GitHub and PyPI;
- current `v1.0.1` installation commands in the public operator guides;
- patch-version support in the v1.0 evidence gate and public version checks.

No resource family, CLI command, MCP tool, configuration schema or controller
operation changed in this release.

## Verification

The protected release workflow runs the full CI matrix, builds and installs the
wheel and source distribution, publishes checksums and provenance, publishes
through PyPI Trusted Publishing, creates the GitHub Release and verifies the
public PyPI files and attestations.

The public artifacts are the [GitHub Release v1.0.1](https://github.com/Opperiesen/lanweave/releases/tag/v1.0.1),
the [PyPI package](https://pypi.org/project/lanweave/1.0.1/) and the annotated
[v1.0.1 tag](https://github.com/Opperiesen/lanweave/tree/v1.0.1).
