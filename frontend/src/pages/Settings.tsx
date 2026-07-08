import { useEffect, useState } from 'react'
import { Card, Input, Button, message, Spin, Typography, Table, Popconfirm } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { listSlackConfigs, saveSlackConfigs } from '../api'
import type { SlackConfigItem } from '../api'

const { Text } = Typography

export default function Settings() {
  const [configs, setConfigs] = useState<SlackConfigItem[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    listSlackConfigs()
      .then(r => setConfigs(r.configs || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const addRow = () => {
    setConfigs([...configs, { name: '', token: '', channel: '' }])
  }

  const deleteRow = (idx: number) => {
    setConfigs(configs.filter((_, i) => i !== idx))
  }

  const updateField = (idx: number, field: keyof SlackConfigItem, value: string) => {
    setConfigs(configs.map((c, i) => (i === idx ? { ...c, [field]: value } : c)))
  }

  const handleSave = () => {
    const empty = configs.some(c => !c.name)
    if (empty) { message.warning('请填写所有配置的名称'); return }
    setSaving(true)
    saveSlackConfigs(configs)
      .then(() => message.success('Slack 配置已保存'))
      .catch(() => message.error('保存失败'))
      .finally(() => setSaving(false))
  }

  const columns = [
    {
      title: '客户名称', dataIndex: 'name', key: 'name', width: 140,
      render: (_: any, __: any, idx: number) => (
        <Input size="small" placeholder="如：张三" value={configs[idx].name}
          onChange={e => updateField(idx, 'name', e.target.value)} />
      ),
    },
    {
      title: 'Bot Token', dataIndex: 'token', key: 'token',
      render: (_: any, __: any, idx: number) => (
        <Input.Password size="small" placeholder="xoxb-..." value={configs[idx].token}
          onChange={e => updateField(idx, 'token', e.target.value)} />
      ),
    },
    {
      title: '频道 ID', dataIndex: 'channel', key: 'channel', width: 140,
      render: (_: any, __: any, idx: number) => (
        <Input size="small" placeholder="C0XXXXXXXX" value={configs[idx].channel}
          onChange={e => updateField(idx, 'channel', e.target.value)} />
      ),
    },
    {
      title: '', key: 'action', width: 50,
      render: (_: any, __: any, idx: number) => (
        <Popconfirm title="删除？" onConfirm={() => deleteRow(idx)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ]

  if (loading) return <Spin size="large" style={{ display: 'block', marginTop: 120 }} />

  return (
    <div style={{ maxWidth: 800 }}>
      <Card title="Slack 推送配置" style={{ marginBottom: 16 }} className="fade-in-up stagger-1">
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 16, marginTop: 0 }}>
          添加多个客户配置后，在 NASDAQ 100 页面选择发送给指定客户或一键群发。
        </p>

        <Table
          dataSource={configs}
          columns={columns}
          rowKey={(_, idx) => String(idx)}
          size="small"
          pagination={false}
          style={{ marginBottom: 12 }}
        />

        <div style={{ display: 'flex', gap: 8 }}>
          <Button icon={<PlusOutlined />} onClick={addRow}>添加客户</Button>
          <Button type="primary" loading={saving} onClick={handleSave}>保存配置</Button>
        </div>
      </Card>

      <Card title="如何获取 Token？" className="fade-in-up stagger-2">
        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 2, color: 'var(--text-secondary)', fontSize: 13 }}>
          <li>访问 api.slack.com/apps 创建 App</li>
          <li>在 OAuth &amp; Permissions 中添加权限：<Text code style={{ color: 'var(--accent)' }}>chat:write</Text>、<Text code style={{ color: 'var(--accent)' }}>chat:write.public</Text></li>
          <li>Install to Workspace 后复制 Bot User OAuth Token</li>
          <li>在 Slack 中右键频道 - 复制链接 - 提取频道 ID</li>
          <li>邀请 Bot 到频道：<Text code style={{ color: 'var(--accent)' }}>/invite @Bot名称</Text></li>
        </ol>
      </Card>
    </div>
  )
}
