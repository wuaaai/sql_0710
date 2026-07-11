qurant数据库 可以用doker服务  启动
图片加载目录要改成自己的

若需要添加新的数据文件，需要在 region_mapping.json 中添加文件和地区的映射关系，再重新插入向量数据库
1.postgres转向量ingest_data_postgres.py, 重新运行此文件需要删掉static\images下的图片
(qdrant转向量ingest_data.py)
2.运行项目根目录下server.py
3.根目录运行langgraph dev
