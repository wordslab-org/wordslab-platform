# The installer's recipe for this implementation (the exact contract is the
# install/lifecycle spec's concern — #65; this directory is the reserved
# home for it).
#
# The recipe tells the installer how to install the implementation on the
# machine: weights to download (a model part's huggingface URL), engine to
# install (an inference-engine part's github URL), service to configure,
# disk to reserve ([requirements].disk-gb), quota to allocate
# (storage-space parts — the user's install-time choice binds,
# ADR-0031 §3).