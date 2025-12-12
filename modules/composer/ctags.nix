# modules/composer/ctags.nix
{
  config,
  lib,
  pkgs,
  ...
}:

let
  inherit (lib) mkOption types;
  inherit (lib.hm.dag) entryAfter;

  homeDir = config.home.homeDirectory;
  yukoDir = "${homeDir}/.yuko";
  tagsDir = "${yukoDir}/.tags";

  # Some channels may not have nix-doc, so guard it
  hasNixDoc = pkgs ? nix-doc;

  # Explicit store-path binaries so activation doesn’t rely on PATH
  ctagsBin = "${pkgs.universal-ctags}/bin/ctags";
  nixDocBin = if hasNixDoc then "${pkgs.nix-doc}/bin/nix-doc" else "";

in
{
  ########################################
  ## Options
  ########################################
  options.yuko.composer.ctags = {
    enable = mkOption {
      type = types.bool;
      default = true;
      description = "Enable nix-doc + ctags tagging for the .yuko tree.";
    };

    extraConfig = mkOption {
      type = types.lines;
      default = "";
      description = ''
        Extra .ctags configuration appended after the base rules.

        Use this for custom regexes (USL, yuko.* markers, etc.)
        so you don't have to touch ~/.yuko/.ctags directly.
      '';
    };
  };

  ########################################
  ## Config
  ########################################
  config = lib.mkIf config.yuko.composer.ctags.enable {

    #
    # 1) Tools: stable (ctags) + optional nix-doc
    #
    home.packages = [ pkgs.universal-ctags ] ++ lib.optionals hasNixDoc [ pkgs.nix-doc ];

    #
    # 2) Editor-visible .ctags in ~/.yuko/.ctags
    #    This is the config that ctags reads when generating tags-code.
    #
    home.file.".yuko/.ctags".text = ''
      --recurse
      --tag-relative=yes
      --sort=yes

      # Ignore typical junk
      --exclude=.git
      --exclude=result
      --exclude=dist
      --exclude=node_modules
      --exclude=.direnv

      # Base is intentionally minimal; you specialize via
      # yuko.composer.ctags.extraConfig.
      #
      # Example later:
      # --langdef=USL
      # --langmap=USL:.usl
      # --regex-USL=/^sigil[[:space:]]+([A-Za-z0-9_]+)/\1/s,sigil,Sigil,/
    ''
    + "\n"
    + config.yuko.composer.ctags.extraConfig;

    #========
    # 3) Activation: generate Nix tags + code tags + merged tags
    #========
    home.activation.yukoNixTags = entryAfter [ "writeBoundary" ] ''
      if [ -d "${yukoDir}" ]; then
        mkdir -p "${tagsDir}"
        cd "${yukoDir}"

        ########################################
        # Nix tags via nix-doc  → .tags/tags-nix
        ########################################
        if [ -n "${nixDocBin}" ]; then
          echo "YukoNix/ctags: generating Nix tags (${tagsDir}/tags-nix)..."
          tmp_nix_tags="$(${pkgs.coreutils}/bin/mktemp)"
          if "${nixDocBin}" tags >"$tmp_nix_tags" 2>/dev/null; then
            mv "$tmp_nix_tags" "${tagsDir}/tags-nix"
          else
            echo "YukoNix/ctags: nix-doc tags failed (non-fatal)."
            rm -f "$tmp_nix_tags"
          fi
        else
          echo "YukoNix/ctags: nix-doc not available in this pkgs set; skipping Nix tags."
        fi

        ########################################
        # Generic code tags via universal-ctags
        # → .tags/tags-code
        ########################################
        echo "YukoNix/ctags: generating code tags (${tagsDir}/tags-code)..."
        "${ctagsBin}" -R \
          --options="${yukoDir}/.ctags" \
          -f "${tagsDir}/tags-code" \
          .

        ########################################
        # Merge into .tags/tags (unified)
        ########################################
        echo "YukoNix/ctags: merging tags-nix + tags-code → ${tagsDir}/tags..."
        : > "${tagsDir}/tags"

        # Start with code tags (full file)
        if [ -f "${tagsDir}/tags-code" ]; then
          cat "${tagsDir}/tags-code" >> "${tagsDir}/tags"
        fi

        # Append nix tags, but strip header lines starting with !_TAG_
        if [ -f "${tagsDir}/tags-nix" ]; then
          ${pkgs.gnused}/bin/sed '/^!_TAG_/d' "${tagsDir}/tags-nix" >> "${tagsDir}/tags"
        fi
      fi
    '';
  };
}
