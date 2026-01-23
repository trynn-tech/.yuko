{
  description = "i3 configuration";

  xsession.windowManager.i3.config = {
    window.border = 0;
    new_window = 'none';
    # Add a new option to set the workspace layout to 'tabbed'
    workspace_layout = 'tabbed';
  };
}
