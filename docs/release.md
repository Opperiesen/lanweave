# Release verification

Lanweave stable releases are published from protected annotated version tags.
The release workflow runs the complete required CI, builds the wheel and source
distribution, tests both in clean environments, publishes checksums and creates
signed provenance before making the GitHub Release public.

## Install from PyPI

```shell
uv tool install lanweave==1.0.0
lanweave --version
```

The MCP adapter remains optional:

```shell
uv tool install 'lanweave[mcp]==1.0.0'
```

After upgrading a profile-backed installation, inspect the selected adapter
before any target request:

```shell
lanweave capabilities --config config/network.yaml --profile office --output json
```

## Complete the protected Site Manager evidence gate

The v0.3.0 cloud evidence remains a separate read-only gate. The controller
administrator password and the local `UNIFI_API_KEY` are not valid credentials
for the Site Manager API.

1. Sign in to the Ubiquiti Site Manager account, open [Settings → API
   Keys](https://unifi.ui.com/settings/api-keys), and select **Create New API
   Key**. Use the generated key only for this integration; Site Manager API v1
   keys are currently read-only.
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

## v0.4 DNS controller evidence

The v0.4.0 DNS gate uses a separate local Integration API key stored in the
protected secret manager. The authorized test creates, updates and prunes one
unique `lanweave-ci-*` `A` policy, then verifies that the controller is clean:

- [sanitized DNS evidence](evidence/v0.4.0-dns.md);
- Network application `10.5.67`;
- no controller address, site, record name, credential or raw response is
  published.

The live suite is opt-in and guarded by `I_UNDERSTAND`, a `lanweave-ci-*`
prefix, an API-key authentication mode and a dedicated controller target. It
must not be run against a normal production configuration.

## Verify a GitHub Release

Download the release assets into one directory. The checksum file contains
asset names relative to that directory:

```shell
gh release download v1.0.0 --repo Opperiesen/lanweave --dir release-v1.0.0
cd release-v1.0.0
sha256sum -c SHA256SUMS
```

Verify the signed SLSA provenance for the wheel with GitHub CLI:

```shell
gh attestation verify \
  lanweave-1.0.0-py3-none-any.whl \
  --repo Opperiesen/lanweave \
  --source-ref refs/tags/v1.0.0 \
  --signer-workflow Opperiesen/lanweave/.github/workflows/release.yml
```

PyPI distributions are published through Trusted Publishing with GitHub OIDC
and receive PyPI's PEP 740 digital attestations. No long-lived PyPI token is
stored in the repository.

The current v1.0.0 scope is documented in [the roadmap](roadmap-v1.0.0.md),
with [migration-v1.0.md](migration-v1.0.md),
[release-v1.0.0.md](release-v1.0.0.md), the [public Python API](api.md) and
[contract evidence](evidence/v1.0.0-contracts.md). The final protected
controller and release workflow URLs are recorded in the v1.0.0 release issue
after publication. Earlier releases remain documented in their versioned
migration and release notes.
