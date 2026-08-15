# Release verification

Lanweave stable releases are published from protected annotated version tags.
The release workflow runs the complete required CI, builds the wheel and source
distribution, tests both in clean environments, publishes checksums and creates
signed provenance before making the GitHub Release public.

## Install from PyPI

```shell
uv tool install lanweave==0.2.0
lanweave --version
```

The MCP adapter remains optional:

```shell
uv tool install 'lanweave[mcp]==0.2.0'
```

## Verify a GitHub Release

Download the release assets into one directory. The checksum file contains
asset names relative to that directory:

```shell
gh release download v0.2.0 --repo Opperiesen/lanweave --dir release-v0.2.0
cd release-v0.2.0
sha256sum -c SHA256SUMS
```

Verify the signed SLSA provenance for the wheel with GitHub CLI:

```shell
gh attestation verify \
  lanweave-0.2.0-py3-none-any.whl \
  --repo Opperiesen/lanweave \
  --source-ref refs/tags/v0.2.0 \
  --signer-workflow Opperiesen/lanweave/.github/workflows/release.yml
```

PyPI distributions are published through Trusted Publishing with GitHub OIDC
and receive PyPI's PEP 740 digital attestations. No long-lived PyPI token is
stored in the repository.

The next release scope is documented in
[Lanweave v0.2.0 release notes](release-v0.2.0.md), with migration steps in
[migration-v0.2.md](migration-v0.2.md).
