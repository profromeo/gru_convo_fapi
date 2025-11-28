module.exports = {
  apps: [{
    name: "FAPI 4061 gru_chat_fapi",
    script: "/home/liveuser/gru_chat_fapi/venv/bin/gunicorn -b 0.0.0.0:4061 -w 2 main:app --timeout 90 --log-level debug -k uvicorn.workers.UvicornWorker",

  }]
}
