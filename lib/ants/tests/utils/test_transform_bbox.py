# (C) Crown Copyright, Met Office. All rights reserved.
#
# This file is part of ANTS and is released under the BSD 3-Clause license.
# See LICENSE.txt in the root of the repository for full licensing details.
import ants.tests
import iris.coord_systems
from ants.coord_systems import OSGB, UM_SPHERE
from ants.utils import transform_bbox
import re

class TestCommon(object):
    @staticmethod
    def _gen_bbox(minx, miny, maxx, maxy):
        return [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]


class TestSameCS(TestCommon, ants.tests.TestCase):
    # Same coordinate system tests.
    #  - No buffer requires when dealing with the same coordinate system.
    def test_points_inside_projected_crs(self):
        bbox_points = (-180, -80, 10, 80)
        bbox = self._gen_bbox(*bbox_points)
        res = transform_bbox(bbox, UM_SPHERE.crs, UM_SPHERE.crs)
        self.assertEqual(len(res.geoms), 1)
        self.assertArrayAlmostEqual(res.bounds, bbox_points)

    def test_points_crossing_dateline_range(self):
        # Test crossing dateline in 0-360 range.
        bbox_points = (170, -80, 200, 80)
        bbox = self._gen_bbox(*bbox_points)
        res = transform_bbox(bbox, UM_SPHERE.crs, UM_SPHERE.crs)
        self.assertEqual(len(res.geoms), 2)
        boxes = sorted([res.geoms[0].bounds, res.geoms[1].bounds], key=lambda x: x[0])
        self.assertArrayAlmostEqual(boxes[0], (-180.0, -80.0, -160.0, 80.0))
        self.assertArrayAlmostEqual(boxes[1], (170.0, -80.0, 180.0, 80.0))

    def test_points_crossing_dateline_range2(self):
        # Here we capture what happens when we pass points which 'should' wrap
        # in the coordinate system provided - this is incorrect as we will
        # return a single geometry in the projected crs (i.e. on a PlateCarree
        # we would connect these via a straight lines).
        bbox_points = (120, -80, -120, 80)
        current_target = (-120, -80, 120, 80)
        bbox = self._gen_bbox(*bbox_points)
        res = transform_bbox(bbox, UM_SPHERE.crs, UM_SPHERE.crs)
        self.assertEqual(len(res.geoms), 1)
        self.assertArrayAlmostEqual(res.bounds, current_target)


class TestDiffCS(TestCommon, ants.tests.TestCase):
    # Different coordinate system tests.
    def setUp(self):
        self.msg = (
            "Attempting to project bounding box (GeogCS(6371229.0)) beyond "
            "the extent of the target coordinate system limits "
            "(TransverseMercator(.*"
        )
        self.msg = self.msg.replace("(", r"\(")
        self.msg = self.msg.replace(")", r"\)")
        super().setUp()

    def test_points_inside_projected_crs(self):
        """Project a bounding box from the OSGB to UM Sphere.

        Notes
        -----
        The ants OSGB crs is a general transverse mercator crs in iris
        which has different projection limits to the cartopy OSGB crs. The
        projection limits for the ants OSGB are the general limits of a transverse
        mercator and are larger than the cartopy OSGB crs which is restricted to a
        valid domain over the UK.
        """

        bbox_points = (-12, -12, 7e5, 13e5)
        bbox = self._gen_bbox(*bbox_points)
        res = transform_bbox(bbox, OSGB.crs, UM_SPHERE.crs)
        self.assertEqual(len(res.geoms), 1)
        tar = [-9.49660933, 49.76607039, 3.63474423, 61.46518886]
        self.assertArrayAlmostEqual(res.bounds, tar)

    def test_point_lie_beyond_crs_definition(self):
        """Test if the bbox lies outside of the valid domain.

        As the OSGB crs is a regional crs (transverse Mercator), we only
        get sensible projections within a restricted domain. The iris OSGB
        returns the cartopy OSGB crs when converted to a cartopy projection.
        The limits of this domain are (0, 0, 7e5, 13e5).
        """

        osgb_crs = iris.coord_systems.OSGB()
        bbox_points = (-180, -90, 180, 90)
        bbox = self._gen_bbox(*bbox_points)

        with self.assertRaisesRegex(ValueError, self.msg):
            transform_bbox(bbox, UM_SPHERE.crs, osgb_crs)

    def test_point_lie_beyond_crs_definition_ants_osgb(self):
        """Test if the bbox lies outside of the valid domain.

        In this case we define a box which fails for the ants OSGB.
        """
        bbox_points = (-100, -60, -80, -30)
        bbox = self._gen_bbox(*bbox_points)

        with self.assertRaisesRegex(ValueError, self.msg):
            transform_bbox(bbox, UM_SPHERE.crs, OSGB.crs)

    def test_ants_osgb_bounds_clipping(self):
        """Demonstrate bounds clipping for different domains.

        For large enough polygons which reach the projection limits of the
        transverse mercator, the bounds are clipped to large values.
        The values are much larger than the range of valid projection
        for the transverse mercator.

        For example, the transverse Mercator has two singularities at
        lon = 90.0 and lon = -90.0. If we approach these the bounds will
        be clipped. Similarly if we approach +/-90.0 in latitude. These bounds
        are clipped at (-2e7, -1e7, 2e7, 1e7) and are not invertible.
        """
        test_cases = [
            90, 110, 140, 160
        ]

        # origin of the OSGB in lat, lon
        lat_0, lon_0 = 49.0, -2.0

        msg = re.escape(
            "The bounding box in the crs (TransverseMercator) is not invertible"
            " to the original crs (GeogCS)."
        )

        for lon_shift in test_cases:
            with self.subTest():
                bbox_points = (lon_0-lon_shift, lat_0-85, lon_0+lon_shift, lat_0+85)
                bbox = self._gen_bbox(*bbox_points)

                with self.assertRaisesRegex(ValueError, msg):
                    transform_bbox(bbox, UM_SPHERE.crs, OSGB.crs)

