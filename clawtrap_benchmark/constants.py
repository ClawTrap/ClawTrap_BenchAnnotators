TASK_TYPES = [
    "网页信息搜索",
    "网站登录与账号管理",
    "邮件发送与回复",
    "在线表单填写与提交",
    "文件上传与下载",
    "日程与会议管理",
    "在线预约与服务办理",
    "商品搜索、比价与购买",
    "社交媒体与内容发布",
    "报表生成与信息汇总",
]

ATTACK_TYPES = [
    "诱导任务失败的攻击",
    "诱导隐私泄漏的攻击",
    "诱导异常输出的攻击",
    "植入隐患的攻击",
    "影响工具使用的攻击",
]

INTERACTIVE_FORMS = [
    "交互弹窗",
    "非交互弹窗",
    "虚假网页",
    "文本信息注入",
    "恶意文件",
]

REQUIRED_CASE_FIELDS = [
    "task",
    "target",
    "task_type",
    "attack_method",
    "success_states",
    "failure_states",
    "logic",
    "attack_type",
    "interactive_form",
    "metadata",
]
