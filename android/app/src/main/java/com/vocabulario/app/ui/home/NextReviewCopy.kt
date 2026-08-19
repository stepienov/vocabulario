package com.vocabulario.app.ui.home

import com.vocabulario.app.data.local.LocalDashboard

/** Copy „następna powtórka": za X min / za X godz. / jutro / pojutrze / za X dni / tygodni / miesięcy. */
object NextReviewCopy {
    enum class Kind { InMinutes, InOneHour, InHours, Tomorrow, DayAfter, InDays, InWeeks, InMonths }

    data class Result(val kind: Kind, val value: Int = 0)

    fun classify(fromMs: Long, toMs: Long): Result {
        val diffMs = toMs - fromMs
        if (diffMs <= 0) return Result(Kind.InMinutes, 1)

        val diffMinutes = (diffMs / 60_000).toInt()
        if (diffMinutes < 60) return Result(Kind.InMinutes, diffMinutes.coerceAtLeast(1))

        val diffHours = (diffMs / 3_600_000).toInt()
        if (diffHours == 1) return Result(Kind.InOneHour)
        if (diffHours < 24) return Result(Kind.InHours, diffHours)

        val calDays = calendarDaysBetween(fromMs, toMs)
        if (calDays == 1) return Result(Kind.Tomorrow)
        if (calDays == 2) return Result(Kind.DayAfter)
        if (calDays < 14) return Result(Kind.InDays, calDays)
        val weeks = calDays / 7
        if (weeks < 8) return Result(Kind.InWeeks, weeks)
        val months = calDays / 30
        return Result(Kind.InMonths, months.coerceAtLeast(2))
    }

    fun calendarDaysBetween(fromMs: Long, toMs: Long): Int {
        val a = LocalDashboard.startOfDayMs(fromMs)
        val b = LocalDashboard.startOfDayMs(toMs)
        var days = 0
        var cursor = a
        while (cursor < b && days < 400) {
            cursor = LocalDashboard.addDaysMs(cursor, 1)
            days++
        }
        return days
    }
}
