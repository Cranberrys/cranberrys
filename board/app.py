import asyncio
import importlib
import logging
import os
import pathlib
import sys

from ac_api import AcApplication
from setter.ac_api_setter import ac_api_set
from setter.module_setter import module_set, module_dir
from setter.resource_setter import resource_set
from setter.router_setter import router_set

sys.path.append(".")

loop = asyncio.get_event_loop()


class Module:

    def __init__(self, name, path, lib, package, _class, app, loaded=False, enable=False, message=''):
        self.name = name
        self.path = path
        self.lib = lib
        self.package = package
        self._class = _class
        self.app = app
        self.loaded = loaded
        self.enable = enable
        self.message = message


class BoardApplication(AcApplication):
    def __init__(self):
        super().__init__()
        self.module_all = {}
        self.module_loaded = {}
        self.module_enable = {}
        self.need_hot_restart = False
        self.name = 'board'
        with self.data_manager('module') as module:
            if 'enable' not in module:
                module['enable'] = []
            if 'module_manager' not in module['enable']:
                module['enable'] += ['module_manager']
            module_path = pathlib.Path('.') / module_dir
            for module_name in os.listdir(module_path):
                module_path = module_path / module_name
                if module_name in self.module_all:
                    continue
                m_lib = None
                if module_name in module['enable']:
                    try:
                        m_lib, plug_info = self.load_module(module_name)
                    except Exception as e:
                        logging.exception(e)
                self.module_all[module_name] = Module(
                    name=module_name,
                    path=str(module_path),
                    lib=m_lib,
                    app=None,
                    loaded=False,
                    enable=module_name in module['enable'],
                    message=''
                )

    def load_module(self, module_name):
        m_package = f'{module_dir}.{module_name}'
        m_lib = importlib.import_module(m_package)
        if not m_lib.plug_info:
            del sys.modules[m_package]
            return None, {}
        plug_info = m_lib.plug_info
        if 'class' not in m_lib.plug_info:
            del sys.modules[m_package]
            return None, plug_info
        if not issubclass(m_lib.plug_info['class'], AcApplication):
            del sys.modules[m_package]
            return None, plug_info
        return m_lib, plug_info

    def get_module(self, plug_name):
        return self.module_all[plug_name]

    def enable_module(self, module_name):
        asyncio.get_event_loop().call_later(1, self.hot_restart)
        with self.data_manager('module') as module:
            if module_name not in module['enable']:
                module['enable'].append(module_name)
        module = self.get_module(module_name)
        if not module.loaded:
            self.hot_restart()

    def disable_module(self, module_name):
        with self.data_manager('module') as module:
            if module_name in module['enable']:
                module['enable'].remove(module_name)
        module = self.get_module(module_name)
        if module.loaded:
            module.app.cron_job.stop_all()
            self.hot_restart()

    def hot_restart(self):
        self.need_hot_restart = True
        raise KeyboardInterrupt()

    # def load_module(self, module):
    #     if module.loaded:
    #         module.message = '插件已加载'
    #         return None
    #     lib = importlib.import_module(module['module'])
    #     if 'id' not in lib.plug_info:
    #         module['message'] = '配置错误，缺少plug_info.id'
    #         self.unload_module(module)
    #         return None
    #     lib.app['board'] = self
    #     lib.app['board_api'] = AcApi(lib.plug_info['id'], lib.app)
    #     module['loaded'] = True
    #     module['lib'] = lib
    #     module['message'] = '插件加载成功'
    #     self.module_loaded[module['name']] = module
    #     return lib

    # def reload_module(self, module):
    #     if not module['loaded']:
    #         return
    #     lib = importlib.reload(module['module'])
    #     lib.app['board'] = self
    #     lib.app['board_api'] = AcApi(lib.plug_info['id'], lib.app)
    #     module['loaded'] = True
    #     module['lib'] = lib
    #     return lib

    # def unload_module(self, module):
    #     del sys.modules[module['module']]
    #     module['loaded'] = False
    #     module['lib'] = None
    #     self.module_loaded.pop(module['name'])

    pass


def get_app():
    board = BoardApplication()

    resource_set(board)
    router_set(board)
    ac_api_set(board)
    module_set(board)
    return board


if __name__ == '__main__':
    logging.basicConfig(
        format='%(levelname)s: %(asctime)s [%(pathname)s:%(lineno)d] %(message)s',
        level=logging.INFO
    )
    while True:
        app = get_app()
        app.run()
        logging.info('web app stop')
        if app.need_hot_restart:
            asyncio.set_event_loop(asyncio.new_event_loop())
            for module in app.module_all.values():
                if module.lib:
                    del sys.modules[module.path]
                    del module.app
                    del module.lib
                del module
            del app
            logging.info('web app begin hot restart')
        else:
            logging.info('web app now exit')
            break
