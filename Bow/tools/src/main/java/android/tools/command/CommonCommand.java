package android.tools.command;

import android.content.pm.PackageInfo;
import android.text.TextUtils;
import android.tools.Output;

import com.beust.jcommander.Parameter;
import com.beust.jcommander.Parameters;
import com.google.gson.Gson;

import org.ironman.framework.util.ActivityUtil;
import org.ironman.framework.util.NetUtil;
import org.ironman.framework.util.PackageUtil;

import java.util.List;

@Parameters(commandNames = "common")
public class CommonCommand extends Command {

    @Parameter(names = {"--top-package"}, order = 0, description = "Display top-level package")
    private boolean top_package = false;

    @Parameter(names = {"--top-activity"}, order = 1, description = "Display top-level activity")
    private boolean top_activity = false;

    @Parameter(names = {"--apk-file"}, order = 2, description = "Display package file")
    private String apk_path = null;

    @Parameter(names = {"--unix-sock"}, order = 3, description = "Display unix sockets")
    private boolean unix_sock = false;

    @Override
    public void run() throws Exception {
        if (top_package) {
            String packageName = PackageUtil.getTopPackage();
            if (!TextUtils.isEmpty(packageName)) {
                Output.out.print(packageName);
            }
        } else if (top_activity) {
            String activityName = ActivityUtil.getTopActivity();
            if (!TextUtils.isEmpty(activityName)) {
                Output.out.print(activityName);
            }
        } else if (!TextUtils.isEmpty(apk_path)) {
            List<PackageInfo> packages = PackageUtil.getPackages(apk_path);
            if (packages != null && packages.size() > 0) {
                Output.out.print(packages.get(0).applicationInfo.publicSourceDir);
            }
        } else if (unix_sock) {
            Output.out.print(new Gson().toJson(NetUtil.getUnixSockets()));
        }
    }
}
