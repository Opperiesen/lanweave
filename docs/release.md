# Release verification

Lanweave stable releases are published from protected annotated version tags.
The release workflow runs the complete required CI, builds the wheel and source
distribution, tests both in clean environments, publishes checksums and creates
signed provenance before making the GitHub Release public.

## Install from PyPI

```shell
uv tool install lanweave==0.3.0
lanweave --version
```

The MCP adapter remains optional:

```shell
uv tool install 'lanweave[mcp]==0.3.0'
```

After upgrading a profile-backed installation, inspect the selected adapter
before any target request:

```shell
lanweave capabilities --config config/network.yaml --profile office --output json
```

## Complete the protected Site Manager evidence gate

The v0.3.0 cloud claim is not complete until the read-only Site Manager
workflow has exercised a real account. The controller administrator password
and the local `UNIFI_API_KEY` are not valid credentials for this API.

1. Create a dedicated API key in the Ubiquiti Site Manager account. Use it
   only for this integration and restrict its permissions to read-only when
   the account interface exposes that option.
2. Keep the key in the approved secret manager; never put it in YAML, a plan,
   an issue, a shell command, or a public artifact.
3. In the repository settings, open the protected environment
   `unifi-site-manager-integration` and add an environment secret named
   `UNIFI_SITE_MANAGER_API_KEY`.
4. Run [Site Manager integration](https://github.com/Opperiesen/lanweave/actions/workflows/site-manager-integration.yml)
   manually on `main` and approve the protected environment when GitHub asks.
5. Keep the generated sanitized report as the release evidence. It may state
   the API version and test outcome, but must not contain the key, host,
   inventory or raw responses.

The workflow is manual-only, reads hosts, sites and devices, and contains no
cloud mutation suite. If the key is missing or unresolved, it fails before
making a request.

## Verify a GitHub Release

Download the release assets into one directory. The checksum file contains
asset names relative to that directory:

```shell
gh release download v0.3.0 --repo Opperiesen/lanweave --dir release-v0.3.0
cd release-v0.3.0
sha256sum -c SHA256SUMS
```

Verify the signed SLSA provenance for the wheel with GitHub CLI:

```shell
gh attestation verify \
  lanweave-0.3.0-py3-none-any.whl \
  --repo Opperiesen/lanweave \
  --source-ref refs/tags/v0.3.0 \
  --signer-workflow Opperiesen/lanweave/.github/workflows/release.yml
```

PyPI distributions are published through Trusted Publishing with GitHub OIDC
and receive PyPI's PEP 740 digital attestations. No long-lived PyPI token is
stored in the repository.

The v0.3.0 scope is documented in [the roadmap](roadmap-v0.3.0.md). The
previous migration remains available in [migration-v0.2.md](migration-v0.2.md),
and the current migration and release notes are in
[migration-v0.3.md](migration-v0.3.md) and [release-v0.3.0.md](release-v0.3.0.md).
