export interface Message {
  id: number;
  author: 'Me' | 'Assistant' | 'System';
  text: string;
  stamp: Date;
}

export interface ChatResponse {
  answer: string;
  tokens_used?: number;
}
