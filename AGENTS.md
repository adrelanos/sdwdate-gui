Comprehensive tests for sdwdate-gui -- an offscreen unit suite, a wire-protocol
and state fuzzer, and an X11/Wayland/SNI integration suite -- are too
high-volume for human review and live in the AI-maintained dist-ai repo, not
here:

  https://github.com/org-ai-assisted/dist-ai -> usr/share/sdwdate-gui-tests/

Run them against this checkout:

    PYTHONPATH="$PWD/usr/lib/python3/dist-packages" sdwdate-gui-tests              # offscreen unit
    PYTHONPATH="$PWD/usr/lib/python3/dist-packages" sdwdate-gui-tests-integration  # X11/Wayland/SNI
