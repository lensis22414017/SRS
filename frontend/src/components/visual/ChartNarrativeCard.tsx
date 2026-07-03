import React from 'react';
import { Card, Typography, Alert } from 'antd';
const { Text, Paragraph } = Typography;

export default function ChartNarrativeCard(props: { title: string; what: string; finding?: string; decision?: string; nextStep?: string; warning?: string }) {
  return <Card size="small" title={props.title} style={{ marginTop: 12 }}>
    <Paragraph><Text strong>这张图看什么：</Text>{props.what}</Paragraph>
    {props.finding && <Paragraph><Text strong>主要发现：</Text>{props.finding}</Paragraph>}
    {props.decision && <Paragraph><Text strong>对决策的意义：</Text>{props.decision}</Paragraph>}
    {props.nextStep && <Paragraph><Text strong>下一步建议：</Text>{props.nextStep}</Paragraph>}
    {props.warning && <Alert type="warning" showIcon message={props.warning} />}
  </Card>;
}
