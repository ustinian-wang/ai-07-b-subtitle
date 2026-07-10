export const sampleRecords = {
  r1: {
    id: 'r1',
    title: 'B站视频 A',
    source: 'bilibili',
    bvid: 'BV1testA',
    page: 1,
    line_count: 10,
  },
  r2: {
    id: 'r2',
    title: '小红书笔记 B',
    source: 'xiaohongshu',
    note_id: 'note-b',
  },
  r3: {
    id: 'r3',
    title: 'B站视频 C',
    source: 'bilibili',
    bvid: 'BV1testC',
    page: 1,
    line_count: 5,
  },
};

export const sampleFolders = [
  {
    id: 'f-seoul',
    name: '首尔',
    children: [
      {
        id: 'f-gangnam',
        name: '江南',
        children: [],
        records: [sampleRecords.r3],
      },
    ],
    records: [sampleRecords.r1],
  },
  {
    id: 'f-empty',
    name: '空目录',
    children: [],
    records: [],
  },
];

export const sampleTree = {
  folders: sampleFolders,
  uncategorized: [sampleRecords.r2],
  total_count: 3,
};
