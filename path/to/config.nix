{
  programs.helix.enable = true;
  programs.helix.config = {
    xsession.windowManager.i3.config = {
      border = 0;
      new_window_command = "none";
      # Add a comment to explain the change
      # Set the workspace_auto_restore option to false
      workspace_auto_restore = false;
    };
  };
}
