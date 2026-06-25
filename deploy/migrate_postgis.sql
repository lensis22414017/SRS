-- SRS PostGIS 迁移脚本 (竞品完善 H2, 2026-06-24)
-- 将 sites/sampling_points 经纬度 → geometry 点, 建 GIST 空间索引,
-- 支撑竞品空间功能: 热点聚类(DBSCAN) / 邻近场地缓冲 / 空间自相关(Moran's I) / 区域聚合。
-- ⚠️ 仅脚本, 不自动执行; 前置: CREATE EXTENSION IF NOT EXISTS postgis;
-- 适用于 PostgreSQL 12+ / PostGIS 3.0+

-- 1. sites 表: 场地几何 + GIST 索引
ALTER TABLE sites ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);
UPDATE sites SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
  WHERE longitude IS NOT NULL AND latitude IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sites_geom ON sites USING GIST(geom);

-- 2. sampling_points 表: 采样点几何 + GIST 索引
ALTER TABLE sampling_points ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);
UPDATE sampling_points SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
  WHERE longitude IS NOT NULL AND latitude IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sampling_points_geom ON sampling_points USING GIST(geom);

-- 3. 触发器: 经纬度变更时自动维护 geom (保持几何与坐标一致)
CREATE OR REPLACE FUNCTION trg_geom_update() RETURNS trigger AS $$
BEGIN
  NEW.geom = CASE WHEN NEW.longitude IS NOT NULL AND NEW.latitude IS NOT NULL
             THEN ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326) ELSE NULL END;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sites_geom_trg ON sites;
CREATE TRIGGER sites_geom_trg BEFORE INSERT OR UPDATE OF latitude, longitude
  ON sites FOR EACH ROW EXECUTE FUNCTION trg_geom_update();

DROP TRIGGER IF EXISTS sampling_points_geom_trg ON sampling_points;
CREATE TRIGGER sampling_points_geom_trg BEFORE INSERT OR UPDATE OF latitude, longitude
  ON sampling_points FOR EACH ROW EXECUTE FUNCTION trg_geom_update();

-- 4. 空间查询示例 (竞品功能参考, 注释保留供开发使用)
-- 4a. 周边 N 米场地 (geography 单位米):
--   SELECT * FROM sites
--   WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(120.15,30.28),4326)::geography, 5000);
-- 4b. 热点密度聚类 (DBSCAN, 1km 半径, 最少 5 点成簇):
--   SELECT id, ST_ClusterDBSCAN(geom, 1000, 5) OVER () AS cluster_id, latitude, longitude
--   FROM sites WHERE geom IS NOT NULL;
-- 4c. K-邻近污染源 (KNN, 最近 10 个场地):
--   SELECT id, longitude, latitude FROM sites ORDER BY geom <-> ST_SetSRID(ST_MakePoint(120.15,30.28),4326) LIMIT 10;

-- 回滚:
--   DROP TRIGGER sites_geom_trg ON sites; DROP TRIGGER sampling_points_geom_trg ON sampling_points;
--   DROP FUNCTION trg_geom_update();
--   DROP INDEX IF EXISTS idx_sites_geom; DROP INDEX IF EXISTS idx_sampling_points_geom;
--   ALTER TABLE sites DROP COLUMN IF EXISTS geom; ALTER TABLE sampling_points DROP COLUMN IF EXISTS geom;
