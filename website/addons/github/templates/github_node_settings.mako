<script type="text/javascript" src="/static/addons/github/github-node-cfg.js"></script>

<form role="form" id="addonSettings${addon_short_name.capitalize()}" data-addon="${addon_short_name}">

    <div class="container-fluid" style="padding-left: 0px; padding-right: 0px">
        <h4 class="addon-title row">
            <div class="col-md-8">
                GitHub
                <small class="authorized-by">
                    % if node_has_auth:
                            authorized by
                            <a href="${auth_osf_url}" target="_blank">
                                ${auth_osf_name}
                            </a>
                    % endif
                </small>
            </div>
            <div class="col-md-4">
                <small>
                    % if node_has_auth:
                        <a id="githubRemoveToken" class="text-danger pull-right" style="margin-top: 4.8px">
                            Deauthorize
                        </a>
                    % else:
                        % if user_has_auth:
                            <a id="githubImportToken" class="text-primary pull-right" style="margin-top: 4.8px">
                                Import Access Token
                            </a>
                        % else:
                            <a id="githubCreateToken" class="text-primary pull-right" style="margin-top: 4.8px">
                                Create Access Token
                            </a>
                        % endif
                    % endif
                </small>
            </div>

        </h4>
    </div>

    % if node_has_auth:

        <input type="hidden" id="githubUser" name="github_user" value="${github_user}" />
        <input type="hidden" id="githubRepo" name="github_repo" value="${github_repo}" />

        <p> <strong>Current Repo:</strong></p>

        <div class="row">

            <div class="col-md-6">
                <select id="githubSelectRepo" class="form-control" ${'disabled' if not is_owner or is_registration else ''}>
                    <option>-----</option>
                        % if is_owner:
                            % for repo_name in repo_names:
                                <option value="${repo_name}" ${'selected' if repo_name == github_repo_full_name else ''}>${repo_name}</option>
                            % endfor
                        % else:
                            <option selected>${github_repo_full_name}</option>
                        % endif
                </select>
            </div>

            % if is_owner and not is_registration:
                <div class="col-md-6">
                    <a id="githubCreateRepo" class="btn btn-default">Create Repo</a>

                    <button class="btn btn-primary addon-settings-submit pull-right">
                        Submit
                    </button>
                </div>


            % endif

        </div>

    % endif

    ${self.on_submit()}

    <div class="addon-settings-message" style="display: none; padding-top: 10px;"></div>

</form>

<%def name="on_submit()">
    <script type="text/javascript">
        $(document).ready(function() {
            $('#addonSettings${addon_short_name.capitalize()}').on('submit', AddonHelper.onSubmitSettings);
        });
    </script>
</%def>
