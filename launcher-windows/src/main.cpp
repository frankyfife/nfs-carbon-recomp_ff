#include "launcher_window.h"
#include "theme.h"

#include <QApplication>

int main(int argc, char** argv) {
  QApplication::setHighDpiScaleFactorRoundingPolicy(
      Qt::HighDpiScaleFactorRoundingPolicy::PassThrough);
  QApplication app(argc, argv);
  QApplication::setApplicationName(QStringLiteral("NFS Carbon Launcher"));
  QApplication::setApplicationVersion(QStringLiteral(NFSCARBON_LAUNCHER_VERSION));
  nfscarbon::theme::apply(app);

  nfscarbon::LauncherWindow window;
  window.show();
  return app.exec();
}
