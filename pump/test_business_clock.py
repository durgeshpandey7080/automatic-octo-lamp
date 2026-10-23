from datetime import date, datetime, timedelta, timezone as dt_timezone
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from .business_clock import business_date_at, shift_period, shift_deadline


@override_settings(TIME_ZONE='Asia/Kolkata')
class BusinessClockTests(SimpleTestCase):
    def test_rollover_uses_indian_time_not_server_or_utc_calendar_date(self):
        before=datetime(2026,10,23,16,29,tzinfo=dt_timezone.utc)
        self.assertEqual(business_date_at(before),date(2026,10,23))
        self.assertEqual(business_date_at(before+timedelta(minutes=1)),date(2026,10,24))
        self.assertEqual(business_date_at(datetime(2026,10,23,0,tzinfo=dt_timezone.utc)),date(2026,10,23))

    def test_two_shifts_cover_one_continuous_day_with_half_hour_grace(self):
        day=date(2026,10,23)
        start,mid=shift_period(day,1)
        next_start,end=shift_period(day,2)
        self.assertEqual(mid,next_start)
        self.assertEqual(end-start,timedelta(hours=24))
        self.assertEqual(start.date(),day-timedelta(days=1))
        self.assertEqual((mid.hour,end.hour),(10,22))
        self.assertEqual(shift_deadline(day,1)-mid,timedelta(minutes=30))
        self.assertEqual(shift_deadline(day,2)-end,timedelta(minutes=30))

    def test_year_and_leap_day_boundaries(self):
        self.assertEqual(business_date_at(timezone.make_aware(datetime(2026,12,31,22))),date(2027,1,1))
        self.assertEqual(business_date_at(timezone.make_aware(datetime(2028,2,28,22))),date(2028,2,29))

    def test_ambiguous_timestamp_and_invalid_slot_rejected(self):
        with self.assertRaises(ValueError):business_date_at(datetime(2026,10,23,22))
        for number in (0,3,True,'1'):
            with self.assertRaises(ValueError):shift_period(date(2026,10,23),number)
