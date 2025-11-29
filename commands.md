虚拟环境中的python.exe
scraping_app_v0\backend\.venv\Scripts\python.exe 


启动后端Flask服务器：
scraping_app_v0\backend\.venv\Scripts\python.exe scraping_app_v0\backend\run.py



启动前端React服务器：
cd scraping_app_v0/frontend
npm run dev


激活虚拟环境
scraping_app_v0\backend\.venv\Scripts\activate.ps1


运行测试前先：
scraping_app_v0\backend\.venv\Scripts\python.exe -m pytest scraping_app_v0\backend\test\unit\test_http_client_impl.py