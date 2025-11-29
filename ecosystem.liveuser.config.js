module.exports = {
  apps: [{
    name: "FAPI 4466 gru_convo_fapi",
    script: "/home/liveuser/gru_convo_fapi/venv/bin/gunicorn -b 0.0.0.0:4466 -w 2 main:app --timeout 90 --log-level debug -k uvicorn.workers.UvicornWorker",

  }]
}
