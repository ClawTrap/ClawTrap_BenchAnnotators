TASK_ATTACK_TAXONOMY = {
    "信息检索与事实核验": [
        "多来源新闻核验",
        "官方公告与政策查询",
        "产品规格与兼容性核验",
        "医疗与公共安全信息检索",
        "学术资料与引用核验",
    ],
    "电商与采购": [
        "按约束搜索商品",
        "购物车完整性",
        "优惠券与促销规则",
        "供应商采购与审批门槛",
        "商品召回与供应商风险检查",
    ],
    "财务与支付": [
        "发票核对与付款准备",
        "银行账户变更验证",
        "费用报销审核",
        "汇率与税率计算",
        "退款与争议处理",
    ],
    "企业协作与办公": [
        "日历冲突与会议改期",
        "邮件分流与回复草稿",
        "CRM 线索更新",
        "客服工单路由",
        "HR 入职与账号开通",
    ],
    "软件开发与运维": [
        "依赖安装与包名核验",
        "软件更新与补丁应用",
        "API 文档篡改",
        "生产事故诊断",
        "云配置与凭证处理",
    ],
    "身份认证与账号安全": [
        "登录会话过期提示",
        "OAuth 授权范围升级",
        "域名与重定向混淆",
        "MFA 与验证码处理",
        "密码重置与账号恢复",
    ],
    "出行、预订与本地服务": [
        "航班或铁路改签",
        "酒店预订",
        "医疗或公共服务预约",
        "餐厅或活动预订",
        "地图与地址导航",
    ],
    "多轮、持久状态与跨站工作流": [
        "延迟触发攻击",
        "跨站证据污染",
        "目标逐步漂移",
        "持久记忆污染",
        "攻击后的恢复与二次验证",
    ],
}

TASK_TYPES = list(TASK_ATTACK_TAXONOMY)
ATTACK_TYPES_BY_TASK_TYPE = TASK_ATTACK_TAXONOMY
ATTACK_TYPES = [attack for attacks in TASK_ATTACK_TAXONOMY.values() for attack in attacks]

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
