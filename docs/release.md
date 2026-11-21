# ZATHROTH container publishing

The [publish workflow](../.github/workflows/publish-container.yml) runs after a
push to `main` or a manual dispatch. It builds Linux AMD64 and ARM64 images on
native runners and smoke-tests the game, account manager, and database on each
architecture. GitHub Actions publishes the resulting multi-architecture image
to GitHub Container Registry with `latest` and the commit SHA tags.

See the [deployment guide](../README.md) for registry and Compose setup.
