# ====================路径工具模块========================
"""
为整个项目提供统一的绝对路径
俩个方法：
    1.get_project_root:获取项目根目录
    2.get_abspath:获取相对路径在项目中的绝对路径
"""

import os


def get_project_root():
    """
    获取项目所在根目录
    ：return:字符串根目录
    """
    # 当前文件的绝对路径
    current_file_path = os.path.abspath(__file__)  # __file__是当前文件的绝对路径
    # 当前文件所在文件夹路径,当前文件上一级
    current_dir_path = os.path.dirname(current_file_path)
    # 项目所在根目录
    project_root = os.path.dirname(current_dir_path)
    return project_root


def get_abspath(relative_path: str) -> str:
    """
    获取绝对路径
    :param relative_path: 相对路径
    :return: 绝对路径
    """
    project_root = get_project_root()
    return os.path.join(project_root, relative_path)


if __name__ == "__main__":
    print(get_abspath("config/config.json"))
