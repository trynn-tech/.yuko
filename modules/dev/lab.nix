{ pkgs, ... }: {
  home.packages = with pkgs; [
    podman-compose # For multi-container intelligence stacks
    skopeo         # For inspecting container images
    dive           # To look inside your "Intelligence" layers
  ];

  # Set up a dedicated directory for your iterations
  home.file.".local/bin/lab-init".text = ''
    #!/usr/bin/env bash
    echo "Initializing Cybernetics Lab..."
    mkdir -p ~/lab/intelligence-model
    # This is where we will pull your specific AI images later
  '';
}
