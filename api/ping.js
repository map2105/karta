// Serverless function для /ping (мониторинг UptimeRobot)
module.exports = (req, res) => {
  res.json({ status: 'ok', ts: new Date().toISOString() });
};
